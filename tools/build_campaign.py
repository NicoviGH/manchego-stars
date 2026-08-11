#!/usr/bin/env python3
"""build_campaign.py -- inject campaign content into the fireemblem8u decomp build.

Reads campaign data (YAML + authored busts) and writes decomp-native source/asset
files into the fireemblem8u submodule working tree, so a plain `make` compiles a
ROM carrying our content. The generated files are reproducible build artifacts --
restore vanilla with `git -C fireemblem8u checkout <path>`.

Engine/Content boundary (CLAUDE.md): the GENERATOR knows character/chapter names;
the C/asm it EMITS is just data. No campaign name is ever hardcoded in engine C.

--- Milestone A (landed first; the file has since grown far past it): PORTRAITS --
For each named cast member, run the bust through portrait_tool.generate (4 decomp
assets) and overwrite a vanilla portrait slot's source files in
graphics/portrait/. The decomp's generic gbagfx pattern rules rebuild the
.4bpp/.4bpp.fk/.4bpp.lz on the next `make`; patch_portrait_geometry also rewrites
the slot's mouth/eye FaceData in src/portrait_data.c (a PATCHED_DECOMP_FILES
build artifact, restored each build) so our faces blink/talk in the right place.
Milestones B+ (names, class/stats, battle anims, full chapter codegen) live
further down this file -- main() is the authoritative pass list.

Milestones B+ (characters, chapter, dialogue codegen) hang off the same CLI.
"""

import argparse
import collections
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile

# portrait_tool lives next to us in tools/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_tool  # noqa: E402
import map_sprite_tool  # noqa: E402
import ref_to_battleframe  # noqa: E402  faked-battle-anim asset generator (#65)
import feditor_to_banim  # noqa: E402  FEditor->decomp battle-anim importer (#90)
import gen_chapter_title  # noqa: E402
import gen_subtitle_cards  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402
from inject.decomp import (  # noqa: E402  shared decomp paths + patch primitives
    REPO, DECOMP, _find_brace_block, _replace_brace_block,
    BATTLEQUOTES_C, BMUNIT_C, LORDSEL_FLAG_BASE,
    WEAPON_ITEM_ENUM, fe_item_enum)  # shared weapon<->ITEM map (used by inject_prologue)
from inject import engine_hooks  # noqa: E402  campaign-agnostic engine C-source hooks
# The host-slot registry. Stdlib-only and OWNED there so tools/check.py can lint it in the
# CI job that has no Pillow; re-exported here so the constants read the same at every call
# site below (#241).
from inject.hosts import (  # noqa: E402,F401
    PROLOGUE_CHAPTER_INDEX, PROLOGUE_HOST_INDEX, PROLOGUE_EVENT_GROUP,
    CH01_HOST_INDEX, CH01_EVENT_GROUP, CH02_HOST_INDEX, CH02_EVENT_GROUP,
    CH03_HOST_INDEX, CH03_EVENT_GROUP, CH04_HOST_INDEX, CH04_EVENT_GROUP,
    CH05_HOST_INDEX, CH05_EVENT_GROUP,
    HostedChapter, hosted_chapters, injector_chapters, undeclared_injectors)

PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')
# Palette index 0 of an FE8 bust is the transparent key, and our authored busts all carry
# magenta there (see campaigns/*/portraits/*.png). Named because _vendor_mug_to_bust has to
# WRITE it, not just read it: a community mug arrives keyed on whatever green its artist used.
PORTRAIT_TRANSPARENT_RGB = (255, 0, 255)
CHARACTERS_C = os.path.join(DECOMP, 'src', 'data_characters.c')
CLASSES_C = os.path.join(DECOMP, 'src', 'data_classes.c')
CLASSES_H = os.path.join(DECOMP, 'include', 'constants', 'classes.h')
# Faked battle anims (#65): the decomp files the injection appends to / patches.
BANIM_DATA_C = os.path.join(DECOMP, 'src', 'banim_data.c')
BANIM_POINTER_H = os.path.join(DECOMP, 'include', 'banim_pointer.h')
BANIMCONF_C = os.path.join(DECOMP, 'src', 'data_banimconf.c')
BANIMCONFUNK_C = os.path.join(DECOMP, 'src', 'data_banimconfunk.c')  # gUnitSpecificBanimConfigs
BANIM_EKRBATTLE_H = os.path.join(DECOMP, 'include', 'ekrbattle.h')
BANIM_LINKER = os.path.join(DECOMP, 'linker_script_banim.txt')
BANIM_DATA_DIR = os.path.join(DECOMP, 'data', 'banim')
BANIM_GFX_DIR = os.path.join(DECOMP, 'graphics', 'banim')
ITEMS_C = os.path.join(DECOMP, 'src', 'data_items.c')
TEXTS_TXT = os.path.join(DECOMP, 'texts', 'texts.txt')
PORTRAIT_DATA_C = os.path.join(DECOMP, 'src', 'portrait_data.c')
# Our busts are all framed identically: the mouth window sits at tile (col 2, row 6)
# and eyes at (col 3, row 4) -- the geometry portrait_tool extracts the mouth from, and
# the same xMouth/yMouth/xEyes/yEyes the Eirika/Franz/Vanessa/Neimi slots already carry
# (those render our busts cleanly). Slots whose FaceData uses different coords (Seth,
# Gilliam, Moulder = 2,5; Ross = 3,6; Garcia = 2,5; Colm = 3,5) make the engine overwrite
# the mouth window one tile off -> a second, offset mouth. Normalize every dressed slot.
PORTRAIT_GEOMETRY = '2, 6, 3, 4'   # xMouth, yMouth, xEyes, yEyes
# Test-chapter spawn (Milestone B step 3): we hijack the vanilla Ch1 ally roster to
# stand up our classed cast on one real map -- the first in-engine confirmation of
# names + portraits + classes + stats together. It touches the three ch1-event files
# below (udefs + eventinfo + eventscript).
CH1_UDEFS_H = os.path.join(DECOMP, 'src', 'events', 'ch1-eventudefs.h')
CH1_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch1-eventinfo.h')
CH1_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch1-eventscript.h')
PROLOGUE_WM_H = os.path.join(DECOMP, 'src', 'events', 'prologue-wm.h')
GAMECONTROL_C = os.path.join(DECOMP, 'src', 'gamecontrol.c')
BMIO_C = os.path.join(DECOMP, 'src', 'bmio.c')
# Opening montage (#43): the lore crawl rides vanilla's 7 prerendered subtitle
# slides (opsubtitle.c walks gOpSubtitleGfxLut with hardcoded transitions).
OPSUBTITLE_C = os.path.join(DECOMP, 'src', 'opsubtitle.c')
OP_SUBTITLE_GFX_DIR = os.path.join(DECOMP, 'graphics', 'op_subtitle')
DATA_OPSUBTITLE_S = os.path.join(DECOMP, 'data', 'data_opsubtitle.s')
# Campaign event BGs (#22): vendored winter backdrops appended as NEW gConvoBackgroundData
# slots (inject_backgrounds). Additive -- never reskin a vanilla BG entry.
DATA_BG_S = os.path.join(DECOMP, 'data', 'data_bg.s')
EVENTSCR2_C = os.path.join(DECOMP, 'src', 'eventscr2.c')
BG_H = os.path.join(DECOMP, 'include', 'bg.h')
BACKGROUNDS_H = os.path.join(DECOMP, 'include', 'constants', 'backgrounds.h')
BG_GFX_DIR = os.path.join(DECOMP, 'graphics', 'bg')
# World-map tour (#43): the two Icewind Dale drawn maps ride the WM_SHOWDRAWNMAP
# slot (worldmap_rm.c GmapRm_StartUpdateDirect).
WORLDMAP_RM_C = os.path.join(DECOMP, 'src', 'worldmap_rm.c')
WORLD_MAP_GFX_DIR = os.path.join(DECOMP, 'graphics', 'world_map')
TOUR_TEXT_ID = 0x8DB   # vanilla's WM narration message, referenced only here
# Map (overworld) sprites (#38). FE8 map sprites are CLASS-driven (GetUnitSMSId ->
# pClassData->SMSId), so two cast on the same class share one sprite and enemies of
# that class would inherit a swap. We instead give each cast member a custom SMS slot
# and a per-CHARACTER override in GetUnitSMSId -- stock classes and vanilla enemies
# untouched. Classes top out at SMSId 106 (verified), so 107+ is free in both the
# wait array (extended here) and the move table (dead tail; no class reaches it).
UNIT_ICON_WAIT_C = os.path.join(DECOMP, 'src', 'unit_icon_wait_data.c')
UNIT_ICON_WAIT_S = os.path.join(DECOMP, 'data', 'const_data_unit_icon_wait.s')
UNIT_ICON_POINTER_H = os.path.join(DECOMP, 'include', 'unit_icon_pointer.h')
WAIT_GFX_DIR = os.path.join(DECOMP, 'graphics', 'unit_icon', 'wait')
CUSTOM_SMS_BASE = 107
# The hover/selected + walking sprite is the per-class MU sheet (gMuInfoTable ==
# unit_icon_move_table, a MuInfo{img, anim} view; 32x480 = 15x 32x32). MuProc carries
# ->unit, so a per-character override of GetUnitMU's .img (reusing the class .anim/motion)
# gives a custom walk without touching classes/enemies. Asset: map_sprites/<id>_mu.png.
MU_C = os.path.join(DECOMP, 'src', 'mu.c')
UNIT_ICON_MOVE_C = os.path.join(DECOMP, 'src', 'unit_icon_move_data.c')
UNIT_ICON_MOVE_S = os.path.join(DECOMP, 'data', 'const_data_unit_icon_move.s')
MOVE_GFX_DIR = os.path.join(DECOMP, 'graphics', 'unit_icon', 'move')
BMUDISP_C = os.path.join(DECOMP, 'src', 'bmudisp.c')
PREP_UNITSELECT_C = os.path.join(DECOMP, 'src', 'prep_unitselect.c')
UNITLISTSCREEN_C = os.path.join(DECOMP, 'src', 'unitlistscreen.c')
# New-game boots straight into the test chapter (skip the vanilla prologue) so the
# spawn is one "New Game" away. CHAPTER_L_1 = 0x01 (constants/chapters.h).
TEST_CHAPTER_INDEX = 1

# --- Prologue chapter (#20) -------------------------------------------------------
# The real New Game target: our designed ch00 ("A Dagger of Ice") on a winter map --
# Scramsax (strong Jagen) + frail Hlin vs Sephek (boss, escapes) + 2 guards. Replaces
# the test-chapter spawn as main()'s in-engine entry. Design SoT:
# campaigns/.../chapters/ch00-prologue-a-dagger-of-ice.yaml.
PROLOGUE_UDEFS_H = os.path.join(DECOMP, 'src', 'events', 'prologue-eventudefs.h')
PROLOGUE_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'prologue-eventinfo.h')
PROLOGUE_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'prologue-eventscript.h')
# PROLOGUE_CHAPTER_INDEX / PROLOGUE_HOST_INDEX / PROLOGUE_EVENT_GROUP: inject/hosts.py.
# Cold-open guests ride vanilla character slots that are NOT in PORTRAIT_MAP, so their
# names/portraits are free placeholders until custom art (see [[feedback_nicolas_not_an_artist]]).
# Sephek rides the vanilla prologue boss slot (ONEILL) so he inherits its CA_BOSS
# attribute -> DefeatBoss fires on his death with no extra flagging. Guards stay
# generics (0x80/0x82) like vanilla. These are display-name/lord-quote slots only;
# class/level/stats come from the UnitDefinition below, not the slot's character data.
PROLOGUE_HLIN_SLOT = 'NATASHA'      # frail must-survive lead (our "lord")
PROLOGUE_SCRAMSAX_SLOT = 'KYLE'     # strong veteran (our "Jeigan")
PROLOGUE_SEPHEK_SLOT = 'ONEILL'     # boss (recurring villain; escapes in the ending)
PROLOGUE_LAYOUT = ('Ch00PrologueMap', 'ch00-prologue')  # (asset label, maps/ source stem)
PROLOGUE_CHAPTER_YAML = 'ch00-prologue-a-dagger-of-ice.yaml'

# Cold-open guests can also wear a custom overworld sprite via the same SMS/MU machinery as
# the cast (inject_map_sprites) -- but their sheets are drawn to FE8's STANDARD player
# map-sprite palette (unit_icon_pal_player), so they render through the normal blue faction
# bank and take NO bespoke cast palette (unlike the cast's purple-bank override). Guests
# have no pcs/npcs YAML, so each sprite's metadata lives here:
#   (uid, slot, class_enum, donor_base)
# donor_base names the vanilla class whose SMS frame geometry the IDLE sheet matches, read
# from the decomp (Pirate = 16x16 axe infantry, matching Hlin's 3-frame 16x16 idle); like
# braulo's base it is a geometry token only, decoupled from the unit's actual class.
PROLOGUE_GUEST_SPRITES = [
    ('hlin-trollbane', PROLOGUE_HLIN_SLOT, 'CLASS_FIGHTER', 'Pirate'),
]

# --- Chapter 1 (#21): "The Iron Trail" ---------------------------------------------
# Hosted on chapter slot 2 (CHAPTER_L_2): ch00's ending hands off with MNC2(0x2), and
# slot-N+1 hosting keeps every campaign chapter on a normal vanilla slot (same dodge
# as the prologue's slot-0 avoidance). Design SoT: chapters/ch01-the-iron-trail.yaml.
CH2_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch2-eventinfo.h')
CH2_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch2-eventscript.h')
CH3_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch3-eventinfo.h')
CH3_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch3-eventscript.h')
EVENTS_UDEFS_C = os.path.join(DECOMP, 'src', 'events_udefs.c')
# CH01_HOST_INDEX / CH01_EVENT_GROUP: inject/hosts.py.
# The goal WINDOW + status-objective strings are message ids, and hosted chapters used to inherit
# them from whatever donor slot `_retarget_host_chapter` copied -- which silently shared them
# between chapters (#207). Every hosted chapter now DECLARES its pair, so `assert_message_ids_unique`
# can bind on them. ch01/ch02/ch03 keep the ids their donors already gave them (measured by running
# the injector -- HEAD and the working tree both lie about post-injection goal ids); only ch04 had
# to move, because its donor IS ch02's host slot.
CH01_GOAL_WINDOW_MSG = 0x19F     # vanilla slot 1's seize window ("Seize camp" is ours)
CH01_GOAL_STATUS_MSG = 0x1A3
CH01_LAYOUT = ('Ch01IronTrailMap', 'ch01-the-iron-trail')  # (asset label, maps/ stem)
CH01_CHAPTER_YAML = 'ch01-the-iron-trail.yaml'
CH01_BOSS_SLOT = 'BREGUET'   # vanilla Ch1's boss slot: CA_BOSS + hand-authored
                             # armor-knight boss bases -- the chief is a Breguet mirror
# Where the cast stands when the join-LOAD runs (pre-prep; PREP hides everyone and
# redeploys the picked 4 onto the YAML deploy_slots, so these only need to be legal
# tiles): a 5x2 block on the west trail mouth around the deploy zone.
CH01_JOIN_POSITIONS = [(c, r) for r in (8, 9) for c in range(1, 6)]
# Enemy AI byte vectors, mirrored from vanilla Ch1's own unit definitions
# (git HEAD src/events/ch1-eventudefs.h) per the YAML's ai_pattern labels.
CH01_AI = {
    'hold_then_attack': '{0x0, 0x3, 0x9, 0x0}',   # vanilla Ch1 soldier line
    'aggressive':       '{0x0, 0x0, 0x1, 0x0}',   # vanilla Ch1 fighter pursuit
    'hold_position':    '{0x3, 0x3, 0x9, 0x20}',  # Breguet: attack in place, never move
    'reinforce':        '{0x0, 0x0, 0x9, 0x0}',   # vanilla Ch1 reinforcement wave
}
CH01_ITEM_IDS = {'iron-lance': 'ITEM_LANCE_IRON', 'iron-axe': 'ITEM_AXE_IRON'}
CH01_CLASS_IDS = {'soldier': 'CLASS_SOLDIER', 'fighter': 'CLASS_FIGHTER',
                  'armor-knight': 'CLASS_ARMOR_KNIGHT'}

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
LORDSEL_CONFIRM_MSGS = (0x959, 0x95A, 0x95B, 0x95C, 0x95D, 0x95E, 0x95F,
                        0x962, 0x963, 0x964)  # same dead pool, one per candidate
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
LORDSEL_PITCH_MSGS = (0x967, 0x968, 0x969, 0x96A, 0x96B, 0x96C, 0x96D,
                      0x96E, 0x96F, 0x970)  # one per candidate (cast capped at 10)
LORDSEL_HEADER_MSG = 0x971   # "Choose your lead" prep-screen header (#46); same dead pool
# The one-time "(a) explain" box (feedback #4): drawn once before the pick loop. Locked
# gist (decisions.md / #46): the chosen hero is the must-survive lead for the whole
# campaign. Faithful to the gist; final wording is Nicolas's render-review call.
LORDSEL_EXPLAINER_TEXT = (
    "One of you must lead the company. Your chosen hero carries the whole "
    "campaign -- if they fall in battle, the war is lost. Choose well."
)
# Beat 1 (#21) "The Northlook" scenic opening: a location card + one message per
# beat (A-E), all riding dead vanilla Ch1-tutorial slot-2 message ids (the prologue
# host strips Ch1's tutorial event lists, so these never display in our ROM).
CH01_BEAT1_CARD_MSG = 0x945
CH01_BEAT1_MSGS = (0x940, 0x941, 0x942, 0x943, 0x944)  # A,B,C,D,E (0x945 = card)
# ch01 ending "The Rolling Cheddar" (#21): a "Bryn Shander" location card + one message
# per beat (A-F), on the dead slot-2 pool (see Beat 1). RESOLVED (#125, 2026-07-05):
# 0x949/0x94A/0x94B/0x94C are ALSO TEXTSHOWn by the tutorial-mode trade demo compiled
# into src/bmtrade.c (EventScr_TradeTut_SelectItem etc.), which nothing patches -- but
# that demo is gated on CheckTradeTutorial() -> CheckFlag(0x87), and flag 0x87 has
# exactly one setter in the whole decomp: ENUT(0x87) inside
# EventScr_Ch1Tut_TradeSelectGalliamEnd (events/ch1-tutorials.h), part of vanilla's
# REAL Ch1 slot (Ch1Events, data_8B363C.s) -- a separate ROM asset from PrologueEvents,
# which is the only slot our chapter progression ever loads (New Game redirects to
# PROLOGUE_HOST_INDEX; see _redirect_new_game). Vanilla Ch1 never loads in our build, so
# flag 0x87 can never be set, CheckTradeTutorial() always returns false, and the trade
# demo (and this msg-id collision) is provably unreachable -- no emulator repro needed.
CH01_ENDING_CARD_MSG = 0x94C
# AB,C,D,E1,E2(narration),E2b(Marty/Baxby),F. 0x93D is a dead vanilla Ch1-tutorial
# slot-2 id (weapon-triangle blurb, stripped by the prologue host) reused for the
# faceless "Marty leans in..." narration that #58 split into its own opaque box.
CH01_ENDING_MSGS = (0x946, 0x947, 0x948, 0x949, 0x93D, 0x94A, 0x94B)
CH01_BODY_MSG = 0x956    # the dismembered sled-driver (dead vanilla Ch2 slot-2 scene id)
CH01_TAUNT_MSG = 0x960   # Izobai's turn-1 boss taunt (no vanilla event-script ref at all)
# Per-PC death quotes (#6, dialogue pass 2026-06-17): one universal dying line per
# deployable cast member, shown with their bust when they fall in ANY chapter. Each
# rides a dead slot-2 message id: 0x94D-0x953 are Ch1-tutorial ids (stripped by the
# prologue host); pinky's 0x958 is a vanilla Ch2 scene id, dead because inject_ch01
# replaces the slot-2 events; trex's 0x965 is the Ephraim/Eirika training-flashback
# tutorial scene, and baxby's 0x93E is the "visit a home / place the cursor" Ch1 cursor
# tutorial -- both dead the same way the prologue host strips the FE8 tutorial path.
# All vetted unreferenced elsewhere -> safe campaign-wide.
# Keyed by cast unit_id; the PC rides its PORTRAIT_MAP slot, so pid/FID = CHARACTER_<slot>.
PC_DEATH_QUOTE_MSGS = {
    'braulo':     0x94D,
    'marty':      0x94E,
    'wolfram':    0x94F,
    'meesmickle': 0x950,
    'prof-rbg':   0x951,
    'rootis':     0x952,
    'sclorbo':    0x953,
    'pinky':      0x958,
    'trex':       0x965,
    'baxby':      0x93E,
    'lupin':      0x974,   # dead vanilla slot (no TEXTSHOW/.msg ref). TODO(#24): auto-allocate
                           # death-quote ids from a free pool so new recruits need only YAML.
    # ch05's pair (#25), picked the same way and from the same neighbourhood as Lupin's: dead
    # vanilla TUTORIAL bodies (0x97A "Now select Staff and press...", 0x97B "Ross has been
    # rescued...") that no TEXTSHOW, .msg or .msgId reaches. The audit that found them excludes
    # include/constants/msg.h, which #defines EVERY id and so marks every slot "referenced",
    # and ignores bare-hex matches, which collide with unrelated addresses -- Lupin's own 0x974
    # fails both of those looser tests while being genuinely free, which is the control.
    'basil':      0x97A,
    'sahnar':     0x97B,
}
# Dev placeholder -- the reusable "next chapter isn't built yet" landing. A chapter whose
# `unlocks_chapter` target isn't hosted yet ends HERE instead of MNC2'ing onto an unbuilt
# slot (which would drop the player on a leftover vanilla map): RBG delivers a cheese-pun
# "thanks for playtesting" line over the campfire BG, then MNTS returns to the title
# screen (a pure event scene -- no map/units needed). Punt it forward (call
# dev_placeholder_scene) at each new chapter boundary until the real next chapter lands.
# See docs/decisions.md "Dev placeholder".
DEV_PLACEHOLDER_MSG = 0x954   # free slot-2 id (the old unused "ingots recovered" body)
DEV_PLACEHOLDER_SPEAKER = 'prof-rbg'   # RBG, the company's over-engineer (Moulder slot)
DEV_PLACEHOLDER_LINE = (
    "Ah -- mind the edge there, friends! That's as far as we've built the world. "
    "The rest is still curing down in the cellar -- you can't rush a good wheel, you "
    "know. Thank you kindly for playtesting! Hold your whey... there's a great deal "
    "more adventure left to age. Come back when it's ripe."
)
# Scenic BG the lord-select menu plays over (NOT the battle map). A standalone "choose
# your leader" screen. Darkling Woods -- "the most Icewind Dale of the options" (Nicolas,
# 2026-06-16). Swap freely to any backgrounds.h enum.
CH01_LORDSEL_BG = 'BG_DARKLING_WOODS'

# ── Ch2 "Cold Welcome" (#22): hosted on chapter slot 3 (ch01's MNC2(0x3) target) ──
# Party PERSISTS from ch01 (no cast re-LOAD); the prep flow fields 5 of the saved roster
# (cap = UnitDef_Event_Ch3Ally entry count) and force-deploys the ch01-chosen lord
# (flag-driven, IsCharacterForceDeployed_ -- no per-chapter wiring). DefeatAll: the slot-3
# host goal is swapped to vanilla slot-4's defeat_all template and the vanilla Ch3
# Seize(14,1) is dropped, so CountRedUnits() drives the rout win; CauseGameOverIfLordDies
# already sits in EventListScr_Ch3_Misc.
# CH02_HOST_INDEX / CH02_EVENT_GROUP: inject/hosts.py.
CH02_GOAL_WINDOW_MSG = 0x19E     # vanilla slot 4's defeat_all window
CH02_GOAL_STATUS_MSG = 0x1A6
CH02_LAYOUT = ('Ch02ColdWelcomeMap', 'ch02-cold-welcome')  # (asset label, maps/ stem)
CH02_CHAPTER_YAML = 'ch02-cold-welcome.yaml'
CH02_BOSS_SLOT = 'BAZBA'      # vanilla Ch3's boss slot -- Halvar mirror (custom bust #19 later)
CH02_MINIBOSS_SLOT = 'BONE'   # vanilla Ch2's named mid-tier, idle on slot 3 -- Grukk (bust later)
# Off-map recruit join-LOAD (#23): Baxby (won over in the ch01-ending cutscene) enters the
# saved party HERE, his first prep roster. A free vanilla-Ch3-region UnitDef symbol (externed,
# unused by our ch02 flow); LOAD1'd blue before the PREP CALL -> Pick Units lists him. The join
# tile is a walkable NW deploy slot (PREP hides everyone and re-picks, so the tile only needs
# to be valid + collision-free at LOAD time -- clear of the chwinga/raiders).
CH02_RECRUIT_JOIN_SYMBOL = 'UnitDef_088B476C'
CH02_RECRUIT_JOIN_POS = (2, 4)
# Vellynne Harpell (recurring Brotherhood NPC) has no map unit in ch02; her CUTSCENE FACE
# rides FID_Ismaire -- a regal vanilla woman absent from our ch00-08 chapters, collision-free.
# Her custom bust (#19) is OPTIONAL: this is a flagged placeholder until that art lands.
CH02_VELLYNNE_SLOT = 'ISMAIRE'
CH02_FISHER_FID = '[FID_VillagerOldMan]'   # the brittle Targos fisher -- generic villager mug
CH02_OPENING_BG = 'BG_NORMAL_VILLAGE'      # Bryn Shander west gate (vanilla village BG)
CH02_ENDING_BG = 'BG_MS_TARGOS_WINTER'     # Targos at nightfall -- vendored snow-town (inject_backgrounds)
# Enemy AI byte vectors + class/item maps (FE8-valid, mirrored from ch01's proven set).
CH02_AI = {
    'aggressive':    '{0x0, 0x0, 0x1, 0x0}',    # pursue/charge
    'hold_position': '{0x3, 0x3, 0x9, 0x20}',   # boss/miniboss: attack in place, never move
    'reinforce':     '{0x0, 0x0, 0x9, 0x0}',    # reinforcement wave
    'cautious':      '{0x0, 0x3, 0x0, 0x0}',    # green chwinga: AttackInRangeAI -- defend, don't pursue (vanilla Garcia)
}
CH02_CLASS_IDS = {'brigand': 'CLASS_BRIGAND', 'archer': 'CLASS_ARCHER',
                  'pegasus_knight': 'CLASS_PEGASUS_KNIGHT'}   # chwinga chassis (balance match to Ross+Garcia)
CH02_ITEM_IDS = {'iron-axe': 'ITEM_AXE_IRON', 'steel-axe': 'ITEM_AXE_STEEL',
                 'iron-bow': 'ITEM_BOW_IRON', 'vulnerary': 'ITEM_VULNERARY',
                 'slim-lance': 'ITEM_LANCE_SLIM', 'hand-axe': 'ITEM_AXE_HANDAXE',
                 'red-gem': 'ITEM_REDGEM', 'elixir': 'ITEM_ELIXIR', 'pure-water': 'ITEM_PUREWATER'}
CH02_GENERIC_PID = '0x8e'    # vanilla slot-3 generic-minion charIndex (autolevelled trash)
# The three GREEN chwinga (protect layer): each rides a distinct minor vanilla NPC slot so
# its survival is individually trackable via CHECK_ALIVE at the ending scene. Slots are
# collision-free (absent from our ch00-08); their map sprite + portrait + name-text
# (Mote/Rime/Glimmer) are the art checkpoint (#38/#39) -- placeholder vanilla faces meanwhile.
# (yaml_id, vanilla character slot). The charm-gift each survivor delivers is NOT stored here --
# it is read from the chapter YAML's green_allies[].gift (single source of truth; the ch02<->ch03
# reward swap lives in the YAML, so a hardcoded copy here silently drifted once -- #23).
CH02_CHWINGA = (
    ('chwinga-mote',    'DARA'),
    ('chwinga-rime',    'KLIMT'),
    ('chwinga-glimmer', 'MANSEL'),
)
# The chwinga wear Sclorbo's chwinga map sprite (he is one), recoloured by the green NPC
# faction palette -- identical green triplets (Nicolas 2026-06-24). Build-time derived from
# this cast sprite; see _inject_ch02_chwinga_sprites.
CH02_CHWINGA_SPRITE_SRC = 'sclorbo'
# Their PORTRAITS are the same move: Sclorbo's bust with the icy-blue glow ramp hue-shifted
# to spirit-green (Nicolas-approved 2026-06-24), build-derived from his portrait (no committed
# asset). Each chwinga's vanilla portrait slot is collision-free (absent from our ch00-08):
# Dara reuses FE8's Saleh-grandmother face (Dara IS Saleh's grandmother), Klimt/Mansel their own.
CH02_CHWINGA_PORTRAIT_SLOT = {'DARA': 'Saleh_Grandma', 'KLIMT': 'Klimt', 'MANSEL': 'Mansel'}
# blue glow ramp -> spirit-green, keyed by SOURCE RGB (robust to palette reordering); the
# same ramp as the map sprite. Everything else (fur collar, tan robe, red tassels) untouched.
CH02_CHWINGA_GLOW_RECOLOR = {
    (96, 211, 219): (150, 230, 160), (113, 188, 214): (140, 205, 150),
    (81, 165, 185): (100, 185, 120), (63, 141, 165): (78, 155, 95),
    (57, 117, 138): (58, 120, 78),
}
# Cutscene message ids -- the dead vanilla Ch3 scene/talk/turn texts our host overwrites
# (referenced ONLY by ch3-eventscript.h scenes we replace; 0x993/0x994 are LIVE battle
# quotes in data_battlequotes.c and are deliberately NOT in this pool -- see decisions.md
# "Ch2 hosting"). Opening (Vellynne): card + 3 beats. Turn-1 archer tutorial: 2. Rear bark:
# 1. Ending (Targos): card + 4 beats. Boss death quote: 1.
CH02_OPENING_CARD_MSG = 0x98b
CH02_OPENING_MSGS = (0x98c, 0x98e, 0x98d)     # A (Vellynne/RBG), B (Meesmickle/Braulo), C (chwinga: Sclorbo's kin + Marty)
CH02_TUTORIAL_MSGS = (0x98f, 0x991)           # turn-1 fliers-vs-bows debut: RBG warns flier Pinky / Pinky
CH02_BARK_MSG = 0x990                         # Wolfram's turn-3 rear-ambush bark (over map)
CH02_ENDING_CARD_MSG = 0x995
CH02_ENDING_MSGS = (0x996, 0x997, 0x998, 0x999)  # A fisher, B Rootis, C narration(#58), D RBG
CH02_BOSS_DEATH_MSG = 0x99a                   # Halvar's death quote (gDefeatTalkList, slot 3)

# FE8's unit-name buffer; longer names overflow and garble the display.
FE_NAME_MAX = 12

# Decomp source files we patch in place. We git-restore them to vanilla at the start
# of every build so injection always runs from a clean base -- idempotent across
# repeated `make`s, and stat-donor growths/ranks always read vanilla values.
PATCHED_DECOMP_FILES = ['texts/texts.txt', 'src/data_characters.c', 'src/portrait_data.c',
                        'src/events/ch1-eventudefs.h', 'src/events/ch1-eventinfo.h',
                        'src/events/ch1-eventscript.h', 'src/events/prologue-wm.h',
                        'src/gamecontrol.c', 'src/bmio.c', 'src/bmunit.c', 'src/bmmap.c',
                        'src/bmcamadjust.c',
                        'src/unit_icon_wait_data.c', 'src/unit_icon_move_data.c', 'src/mu.c',
                        'src/bmudisp.c', 'src/prep_unitselect.c',
                        # #218: both roster screens that blank the purple OBJ bank
                        # (PURPLE_BANK_BLANKERS); prep_unitselect.c is listed above
                        'src/unitlistscreen.c',
                        # lord-select (#46): CallLordSelectMenu decl for eventscripts
                        'include/eventcall.h',
                        # enemy class reskins (#21): cloned goblin classes in gClassData;
                        # classes.h gets new class ids appended past 0x7F (#23 Lizardzerker)
                        'src/data_classes.c', 'include/constants/classes.h',
                        # faked battle anims (#65): appended banim_data row + pointer
                        # externs + linker block; the Archer-CLONE class + its new AnimConf
                        # (data_classes.c already listed); the AnimConf's extern decl
                        'src/banim_data.c', 'include/banim_pointer.h',
                        'src/data_banimconf.c', 'include/ekrbattle.h',
                        # #165 caster-scoped spell-palette tint (green Dark magic): the
                        # _patch_banim_spell_palette_tint hook patches these TUs -- the
                        # GetBanimSpellPaletteTint lookup + StartSpellAnimation seam in
                        # efxmagic; the green recolour + palette-copy wrap in ekrutils; the
                        # dedicated gMSSpellTint overlay global in ekrbattle (declared beside
                        # gEfxSpellAnimExists); its teardown reset in ekrdispup. ekrbattle.h
                        # (the enum/struct/table + gMSSpellTint extern) is listed above.
                        'src/banim-efxmagic.c', 'src/banim-ekrutils.c',
                        'src/banim-ekrbattle.c', 'src/banim-ekrdispup.c',
                        # #183 per-caster charge flash: the _patch_banim_charge_flash hook adds
                        # the pulse proc + arm in banim-efxmisc, arms it from the existing
                        # elec-charge command (case 40) in banim-main, and declares the arm in
                        # efxbattle.h. The gMSChargeFlashes table rides data_banimconfunk.c
                        # (listed below); the struct/extern ride ekrbattle.h (listed above).
                        'src/banim-efxmisc.c', 'src/banim-main.c', 'include/efxbattle.h',
                        'linker_script_banim.txt',
                        # #65 M-B (character-unique anims, no class slot): the per-character
                        # config table gets the AnimConf appended; the combat-lookup engine
                        # hook swaps GetBattleAnimationId -> _WithUnique in ekrbattleintro;
                        # GetBanimPalette in ekrmain gets the custom-banim palette guard
                        'src/data_banimconfunk.c', 'src/banim-ekrbattleintro.c',
                        'src/banim-ekrmain.c',
                        # battle ground platforms (#65): vendored snow/ice grounds appended to
                        # battle_terrain_table + the terrain->ground remap (snow chapters)
                        'src/banim_terrain_data.c', 'data/data_banim_terrain.s',
                        'src/data_terrains.c', 'src/banim-battleparse.c', 'include/variables.h',
                        # nat-20 crit flourish (#11): efx proc hook + asset incbins
                        'src/banim-efxhit.c', 'data/data_banim.s',
                        # Goodberry (#21): vulnerary icon swapped by inject_item_icons
                        'graphics/item_icon/item_icon_vulnerary.png',
                        # pink Tourmaline (#23): the additive pal-2 icon route -- inject_item_icons
                        # reskins the Red Gem tiles, inject_item_icon_pal2 appends its icon
                        # palette, and the _patch_draw_icon_pal2 engine hook routes those iconIds
                        # to reserved BG bank 15. The icon/header hooks are NON-idempotent (their
                        # guard hard-exits on a non-vanilla form), so it MUST restore each build.
                        'src/icon.c', 'include/icon.h', 'graphics/item_icon/item_icon_palette.agbpal',
                        'graphics/item_icon/item_icon_red_gem.png',
                        'data/const_data_unit_icon_wait.s', 'data/const_data_unit_icon_move.s',
                        'include/unit_icon_pointer.h',
                        'data/const_data_chapter_maps.s', 'data/data_8B363C.s',
                        'src/data/chapter_settings.json',
                        'src/events/prologue-eventudefs.h', 'src/events/prologue-eventinfo.h',
                        'src/events/prologue-eventscript.h', 'src/data_battlequotes.c',
                        # ch01 host slot (#21): Ch2 events + the shared udefs TU;
                        # slot 2's title card is regenerated by inject_ch01
                        'src/events/ch2-eventinfo.h', 'src/events/ch2-eventscript.h',
                        # ch03 host slot (#23): Ch4 events (slot 4) rewritten by inject_ch03
                        'src/events/ch4-eventinfo.h', 'src/events/ch4-eventscript.h',
                        # ch04 host slot (#24): Ch5 events (slot 5) rewritten by inject_ch04
                        'src/events/ch5-eventinfo.h', 'src/events/ch5-eventscript.h',
                        # ch05 host slot (#25): slot 6's events. Named "ch6" because FE8
                        # inserted Ch5x at slot 5, so from slot 6 on the slot index and the
                        # vanilla symbol name disagree in the BASE GAME -- see the CH05_*
                        # constant block, which states that offset once for the whole build.
                        'src/events/ch6-eventinfo.h', 'src/events/ch6-eventscript.h',
                        'src/events_udefs.c', 'graphics/chap_title/chap_title_2.png',
                        # host slot's title card (chapTitleId 1); regenerated by
                        # inject_prologue from the chapter YAML's title
                        'graphics/chap_title/chap_title_1.png',
                        # ch02 host slot's title card (chapTitleId 3); regenerated by inject_ch02
                        'graphics/chap_title/chap_title_3.png',
                        # ch03 host slot's title card (chapTitleId 4); regenerated by inject_ch03
                        'graphics/chap_title/chap_title_4.png',
                        # ch04 host slot's title card (chapTitleId 5); regenerated by inject_ch04
                        'graphics/chap_title/chap_title_5.png',
                        # ch05 host slot's title card (chapTitleId 6); regenerated by inject_ch05
                        'graphics/chap_title/chap_title_6.png',
                        # title banner palettes; repointed by inject_title_theme
                        'data/data_A01CC4.s', 'data/data_A21658.s',
                        # opening-montage lore crawl (#43): card slides + LUT timers
                        # + aurora mural incbins, regenerated by inject_opening_montage
                        # on MONTAGE=1 builds
                        'src/opsubtitle.c', 'data/data_opsubtitle.s',
                        # campaign event BGs (#22): inject_backgrounds appends a slot +
                        # enum id + extern decls + incbin symbols per vendored backdrop
                        'data/data_bg.s', 'src/eventscr2.c',
                        'include/constants/backgrounds.h', 'include/bg.h',
                        # world-map tour (#43): drawn-map selector patched in by
                        # inject_world_tour on MONTAGE=1 builds
                        'src/worldmap_rm.c',
                        # battle-map-kind fallback patch (no world map -> STORY)
                        'src/worldmap_path.c',
                        # chapter-title fallback patch (no world map -> ROM chapTitleId,
                        # not a WM skirmish name); regenerated by _patch_chapter_title_wm_fallback
                        'src/chapter_title.c',
                        # lord select (#42): LordSelect_GetPid + force-deploy hook
                        # (eventinfo) and the Seize gate (bmdifficulty); the UnitKill
                        # hook (bmunit.c) and defeat-quote demotions
                        # (data_battlequotes.c) ride files already listed above.
                        # The convoy gate (bmmenu) + the vanilla force-deploy table
                        # (data_event_trigger) are routed through LordSelect too.
                        'src/eventinfo.c', 'src/bmdifficulty.c',
                        'src/bmmenu.c', 'src/data_event_trigger.c',
                        # lord survivability floor (#45 3c): LordFloor_ApplyOnce (eventinfo,
                        # already listed) + its EndPrepScreen call site (prep_sallycursor)
                        'src/prep_sallycursor.c'] + [
                        'graphics/op_subtitle/OpSubtitle_%02d.png' % i
                        for i in range(gen_subtitle_cards.CARD_COUNT)]


# --- warm-rebuild acceleration: idempotent injection ---------------------------
# The injection re-emits (very nearly) byte-identical decomp sources every build,
# but the plain writes -- and restore_vanilla_sources' `git checkout` -- bump each
# touched file's mtime. `make` keys off mtime, so it recompiles the translation
# unit AND re-runs the expensive graphics compression / serial banim link even when
# the CONTENT is unchanged from the last build. The dominant costs are the ~354-TU
# recompile cascade from restored widely-included headers (variables.h, ekrbattle.h,
# classes.h) and the serial `arm_compressing_linker.py` rebuild of data_banim.o
# (1752 assets) whenever any banim sheet/motion/agbpal mtime moves.
#
# Fix: snapshot the previous build's injection footprint (content hash + mtime) up
# front, and once injection finishes, rewind the mtime of every file whose bytes are
# byte-for-byte identical. `make` then treats those targets as up to date. This is
# purely an mtime optimisation -- a file is rewound ONLY when its content is
# unchanged, so the compiled ROM is bit-identical. See docs/decisions.md (Build).

def _decomp_footprint():
    """Absolute paths git reports as modified/untracked under the decomp -- i.e. the
    previous build's injection footprint (source files; the .o/.lz/.4bpp build
    outputs are .gitignored, so they are excluded). Never raises: a git hiccup just
    yields an empty snapshot, which preserves correctness and only skips the speed-up."""
    try:
        out = subprocess.run(
            ['git', '-C', DECOMP, 'status', '--porcelain', '-z', '-uall'],
            check=True, capture_output=True).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    paths = []
    for rec in out.split(b'\0'):
        # porcelain -z record: 'XY <path>' (rename records carry a trailing NUL-
        # separated old path, which harmlessly resolves to a real file too).
        if len(rec) > 3:
            paths.append(os.path.join(
                DECOMP, rec[3:].decode('utf-8', 'surrogateescape')))
    return paths


def _snapshot_mtimes(paths):
    """{abs_path: (mtime_ns, sha1_digest)} for each existing regular file in `paths`."""
    snap = {}
    for p in paths:
        try:
            st = os.stat(p)
            with open(p, 'rb') as f:
                snap[p] = (st.st_mtime_ns, hashlib.sha1(f.read()).digest())
        except OSError:
            pass  # missing / directory / unreadable -> just don't track it
    return snap


def _rewind_unchanged_mtimes(snap):
    """Rewind the mtime of every snapshotted file whose bytes are unchanged, so make
    skips its (redundant) recompile/recompression. Returns the count rewound. Only
    ever touches mtime, and only for byte-identical content -- never file bytes."""
    n = 0
    for p, (mtime_ns, digest) in snap.items():
        try:
            with open(p, 'rb') as f:
                if hashlib.sha1(f.read()).digest() == digest:
                    os.utime(p, ns=(mtime_ns, mtime_ns))
                    n += 1
        except OSError:
            pass
    return n


BUILD_STAMP = os.path.join(REPO, '.build-config.json')


def _stamp_build_config(campaign, flags):
    """Record which boot flags produced the ROM now in the tree.

    A playtest scenario is bound to a ROM configuration -- a CH04BOOT=1 build cannot
    reach ch02's map -- and the most expensive failure mode in this repo is a scenario
    that FAILs for the honest reason "you are running the wrong ROM". Nothing in the
    .gba says how it was built, so record it here; tools/playtest/matrix.py reads this
    and refuses the run instead of letting mGBA time out for 7 minutes.

    Gitignored: it describes the working tree's build artifact, not the source."""
    stamp = {'campaign': campaign,
             'flags': {k: bool(v) for k, v in sorted(flags.items())}}
    try:
        with open(BUILD_STAMP, 'w') as fh:
            json.dump(stamp, fh, indent=2)
    except OSError as exc:      # never fail a build over the stamp
        print('  (could not write %s: %s)' % (BUILD_STAMP, exc))


def restore_vanilla_sources():
    # Restore explicitly from HEAD (not the index): `git checkout -- <file>` pulls from
    # the staging area, so a previously-staged patched file would survive and corrupt the
    # build (e.g. the non-montage monologue-skip leaking into a --montage build). `HEAD --`
    # always resets to the committed vanilla source.
    subprocess.run(['git', '-C', DECOMP, 'checkout', 'HEAD', '--'] + PATCHED_DECOMP_FILES,
                   check=True)

# Our cast wear stock vanilla FE8 classes (docs/decisions.md Class Mapping). Map
# each unit YAML's display class -> the decomp CLASS_ enum. Parenthetical flavor
# like "Mage (Ice)" is stripped before lookup.
CLASS_MAP = {
    'Pirate':         'CLASS_PIRATE',
    'Shaman':         'CLASS_SHAMAN',
    'Archer':         'CLASS_ARCHER',
    'Mage':           'CLASS_MAGE',
    'Priest':         'CLASS_PRIEST',
    'Cleric':         'CLASS_CLERIC',  # Basil (ch05 recruit) -- Priest's twin, but its default
                                       # promotion is Bishop (light), not Sage (anima)

    'Knight':         'CLASS_ARMOR_KNIGHT',
    'Pegasus Knight': 'CLASS_PEGASUS_KNIGHT',
    'Thief':          'CLASS_THIEF',   # Trex (ch03 recruit) -- the army's utility unit
    'Cavalier':       'CLASS_CAVALIER',  # Baxby the axe-beak (ch01 recruit) -- mounted sword/lance
    'Myrmidon':       'CLASS_MYRMIDON',  # Sahnar (ch05 recruit) -- the army's sword crit-duelist
}

# fe_stats key -> the gCharacterData personal-base field it feeds. FE8 unit stats
# are class base + this personal base. There is one attack stat (basePow), shown as
# STR for physical classes and MAG for magic ones. MOV is class-only (handled apart).
STAT_FIELD = {
    'HP': 'baseHP', 'STR': 'basePow', 'MAG': 'basePow', 'SKL': 'baseSkl',
    'SPD': 'baseSpd', 'DEF': 'baseDef', 'RES': 'baseRes', 'LCK': 'baseLck',
    'CON': 'baseCon',
}
# class-data base fields we read (classes carry no luck -> baseLck defaults 0).
CLASS_BASE_FIELDS = ('baseHP', 'basePow', 'baseSkl', 'baseSpd', 'baseDef',
                     'baseRes', 'baseCon', 'baseMov')

# "Do what the actual game does": each cast unit takes the GROWTHS and starting
# WEAPON RANKS of a canonical vanilla FE8 unit of the same class (its stat donor),
# so it levels and fights like a real FE unit of that class -- not an invented
# scheme. Donor data is read from VANILLA data_characters.c (a snapshot taken before
# any patching), so it's correct even when the donor is itself a portrait slot we
# repurpose. Pirate has no permanent PC in FE8 -> Garcia (axe fighter) is the proxy.
STAT_DONOR = {
    'braulo':     'CHARACTER_GARCIA',    # Pirate: no PC pirate in FE8; axe-fighter proxy
    'marty':      'CHARACTER_KNOLL',     # Shaman
    'meesmickle': 'CHARACTER_KNOLL',     # Shaman
    'wolfram':    'CHARACTER_GILLIAM',   # Armor Knight
    'prof-rbg':   'CHARACTER_NEIMI',     # Archer
    'rootis':     'CHARACTER_LUTE',      # Mage
    'sclorbo':    'CHARACTER_MOULDER',   # Priest
    'pinky':      'CHARACTER_VANESSA',   # Pegasus Knight
    'trex':       'CHARACTER_COLM',      # Thief (ch03 recruit) -- vanilla starter thief donor
    'baxby':      'CHARACTER_FRANZ',     # Cavalier (ch01 recruit) -- fresh-cavalier growth runway
    'lupin':      'CHARACTER_KYLE',      # Cavalier (ch04 red->blue parley recruit); Kyle = stat ref only
    # The ch05 pair (#25). Their donors are what makes the two Priests differ and what makes
    # Sahnar a duelist rather than a generic sword: decisions.md prices Sclorbo as the durable
    # war-priest (Moulder) against Basil as the frail mage-healer (Natasha), and that split
    # exists ONLY here -- the YAML design records show identical Priest CLASS data, because
    # they are the same class. Sahnar takes Joshua, the archetype she was locked to.
    'basil':      'CHARACTER_NATASHA',   # Cleric: frail/high-magic, opposite Sclorbo's Moulder
    'sahnar':     'CHARACTER_JOSHUA',    # Myrmidon: the crit-sword duelist; Joshua = stat ref only
}
GROWTH_FIELDS = ('growthHP', 'growthPow', 'growthSkl', 'growthSpd',
                 'growthDef', 'growthRes', 'growthLck')

# Personal-BASE donor (the starting stat line). Usually the same canonical unit as the
# rank donor (STAT_DONOR), but the two shamans take EWAN's Ch1-appropriate bases (Knoll's
# are lv9-inflated). docs/decisions.md "Party-side parity" / issue #45.
BASE_DONOR = dict(STAT_DONOR, marty='CHARACTER_EWAN', meesmickle='CHARACTER_EWAN')

# GROWTH donor (the level-up curve). Same as the rank donor except Meesmickle, who grows
# on EWAN's curve (-> Summoner: dodge/luck) while Marty keeps Knoll's (-> Druid: soak/nuke).
# Ranks stay on STAT_DONOR so both shamans keep Knoll's ITYPE_DARK rank (Ewan is Anima-only,
# so his tome wouldn't equip). docs/decisions.md "Party-side parity" / issue #45.
GROWTH_DONOR = dict(STAT_DONOR, meesmickle='CHARACTER_EWAN')


# our cast bust  ->  vanilla portrait slot whose graphic files we overwrite.
# Slots are FE8's earliest-available cast so one early chapter shows many faces.
# (Started as the portrait mapping; it is now the general character-slot key --
# names, class/stats/growths/gender, death quotes, and map sprites all ride it.)
PORTRAIT_MAP = {
    'braulo':     'Eirika',    # the prologue lord -- first face the player sees
    'marty':      'Seth',
    'wolfram':    'Franz',
    'meesmickle': 'Gilliam',
    'prof-rbg':   'Moulder',
    'rootis':     'Vanessa',
    'sclorbo':    'Ross',
    'pinky':      'Neimi',
    'pepperjack': 'Garcia',
    'brie':       'Colm',
    # ch01 recruit Baxby the axe-beak (npcs/baxby.yaml) -- a classed Cavalier (mount), so a
    # full cast member. Rides the vanilla Forde slot (a Cavalier absent from our ch00-08 ->
    # collision-free); the same slot already carried his ch01-ending CUTSCENE face (he speaks
    # there -- Marty wins him over), and now also his unit/stats/map sprite/death quote. He is
    # recruited by that ENDING cutscene, so he simply rides the ch02+ prep roster (no on-map
    # recruit) -- cast_available_at() handles that from his recruit.chapter (ch01).
    'baxby':      'Forde',
    # ch03 recruit Trex (npcs/trex.yaml) -- a classed Thief, so unlike the two name-only
    # NPCs above he IS a full cast member: he rides the vanilla Rennac slot (a Rogue absent
    # from our ch00-08, referenced nowhere else in the build -> collision-free), which carries
    # his name / class+stats / bust / map sprite / death quote just like every PC. His mid-map
    # green->blue JOIN trigger is wired separately (pairs with the #23 mid-map cutscene); here
    # he is a real deployable unit so his vendored custom sprite renders in his cast colours.
    'trex':       'Rennac',
    # ch04 recruit Lupin (npcs/lupin.yaml) -- a classed Cavalier (the wolf IS the mount), so a
    # full cast member like Trex. Unlike Trex he starts RED (the hostile pack's leader) and is
    # won by Marty's Talk -> CUSA red->blue (the vanilla Joshua pattern), see recruit.initial_faction.
    # Rides the vanilla Duessel slot (a Great Knight absent from our ch00-08, referenced nowhere
    # else -> collision-free); his stat line references Kyle (STAT_DONOR), his identity is Duessel.
    'lupin':      'Duessel',
    # The ch05 recruits (#25). Both shipped their art in #179/#181 and then sat INERT for two
    # months, because art without a slot is art nothing can address: no name, no bust, no stat
    # line, no map sprite, no death quote -- and, the thing that actually blocked the chapter,
    # no pid for a Talk to name. These two lines are that identity.
    # Basil the goodberry shrub (npcs/basil.yaml) rides ARTUR -- a Monk absent from our ch00-08
    # and referenced nowhere else, so dressing it is collision-free. His stat line references
    # Natasha (STAT_DONOR) and his class is hers too (Cleric, 2026-08-08). The slot's own gender
    # does not have to match his: `gender:` in the YAML rewrites .attributes on whatever slot the
    # unit wears (_set_gender), and promotion is keyed by CLASS in gPromoJidLut, never by the
    # character -- so a female Cleric on the male Artur slot promotes Bishop/Valkyrie correctly.
    'basil':      'Artur',
    # Sahnar (npcs/sahnar.yaml) rides MARISA -- vanilla's OTHER red-to-blue Myrmidon parley,
    # absent from our ch00-08 and referenced nowhere else. Exact class match, unlike Trex's and
    # Lupin's slots; her stat line references Joshua (STAT_DONOR), her identity is Marisa.
    'sahnar':     'Marisa',
}

# Ravisin is a chapter boss, not a recruit, so she uses the guest portrait path rather than
# PORTRAIT_MAP's cast-identity machinery. Her approved portrait is Garytop's F2E Aversa mug
# with a strict seven-entry palette substitution: silver hair -> chestnut and warm skin ->
# frost-pale. Nicolas approved this exact mapping on 2026-08-10; the original brown markings
# and every pixel position stay untouched.
RAVISIN_VENDOR_MUG = 'Aversa {Garytop} [F2E].png'
RAVISIN_RECOLOR = {
    (247, 243, 238): (172, 116, 76),
    (219, 216, 224): (140, 88, 56),
    (170, 171, 186): (104, 64, 40),
    (125, 114, 135): (72, 40, 32),
    (227, 207, 182): (240, 232, 232),
    (201, 165, 142): (208, 192, 200),
    (163, 130, 110): (176, 152, 168),
}

# Prologue cold-open guests ride vanilla character slots outside PORTRAIT_MAP
# (PROLOGUE_*_SLOT below); these are the portrait files those slots display.
# Guest busts are OPTIONAL: a missing PNG keeps the vanilla face, so this wiring
# works before (and independent of) the art landing.
GUEST_PORTRAIT_MAP = {
    'hlin-trollbane': 'Natasha',
    'scramsax':       'Kyle',
    'sephek-kaltro':  'O_Neill',
    # ch01 boss Izobai rides the Breguet slot (CH01_BOSS_SLOT); her death-quote FID
    # is FID_Breguet, so dressing that slot with izobai.png shows her green-goblin bust.
    'izobai':         'Breguet',
    # ch01 Foaming Mugs quest-giver Hruna rides the generic Villager_Woman face slot
    # (FID tag [FID_VillagerWoman] = 0x60) -- a throwaway NPC mug used nowhere else,
    # so dressing it with hruna.png is collision-free. Cutscene-only (no map unit).
    'hruna':          'Villager_Woman',
    # ch01-ending patron Duvessa Shane (Speaker of Bryn Shander) rides the Selena slot:
    # her bust is a palette recolor of vanilla Selena (portraits/duvessa.py), and Selena
    # is a late-game Grado boss absent from our MVP chapters (ch00-08), so dressing
    # FID_Selena with duvessa.png is collision-free. Recurring cutscene NPC (no map unit).
    'duvessa':        'Selena',
    # ch02 quest-giver Vellynne Harpell (recurring Arcane Brotherhood necromancer) rides
    # the vanilla Ismaire slot (CH02_VELLYNNE_SLOT) -- a regal woman absent from our ch00-08,
    # collision-free. Her bust is the FE-Repo Sonya (Witch) mug with a snow-white hair recolor
    # (portraits/vellynne.py); cutscene-only (no map unit).
    'vellynne':       'Ismaire',
    # ch03 mid-map RBG-execution beat: the Icewind Brute's snarl now has a mug (Nicolas supplied the
    # ref, 2026-07-11). It rides the vanilla Caellach slot -- a brutish Grado general absent from our
    # ch00-08, referenced nowhere else -> collision-free. Bust = ref_to_bust of the HD kobold-brute
    # ref (flipped to FE8 screen-left, crop 20,90,1970,1710, --zoom 0.70, no sharpen). The zoom is
    # load-bearing: at 1.0 the leftward snout tip fell in FE8's top-left DEAD CORNER (portrait_tool
    # clipped_mask: 408 painted px dropped, the whole nose); 0.70 adds enough top headroom that the
    # snout ships fully intact (0 clipped px -- verified via clipped_mask). Cutscene-only (the Brute
    # is a raw-pid enemy 0xb6; its death quote is silent, so FID_Caellach appears ONLY in the midmap line).
    'kobold-brute':   'Caellach',
    # ch05 boss Ravisin is the raw on-map pid 0xb8, but her cutscene/death-quote face dresses
    # Riev -- a late-game Bishop absent from our ch00-08 and otherwise unused. The raw pid's
    # CharacterData portraitId is bound separately by RAW_PID_PORTRAITS below.
    'ravisin':        'Riev',
}


def _bust_dir(campaign):
    return os.path.join(REPO, 'campaigns', campaign, 'portraits')


def dressed_guest_slots(campaign):
    """Portrait slots of guests whose bust PNG exists (and so get dressed)."""
    return [slot for unit, slot in GUEST_PORTRAIT_MAP.items()
            if os.path.isfile(os.path.join(_bust_dir(campaign), unit + '.png'))]


def dressed_portrait_slots(campaign):
    """EVERY vanilla portrait slot this build overwrites -- cast, guests, the ch02 chwinga and
    the ch05 reliquary residents.

    This exists because dressing a slot and normalizing its mouth/eye geometry are two separate
    steps, and for a long time the second one only knew about the first two groups. A slot that
    is dressed but NOT normalized keeps the vanilla character's mouth window, so the engine
    paints its blink/talk overlay at the old face's coordinates -- over ours. It does not fail
    the build, it does not fail a scenario, and on a face whose mouth happens to sit near
    vanilla's it is invisible; on the other three ch05 residents it smeared a block of skull
    across the eye sockets and doubled the teeth (Nicolas spotted it, 2026-08-09). The ch02
    chwinga had been shipping the same defect unnoticed.

    Conditioned on the asset actually existing, like dressed_guest_slots: normalizing a slot we
    did NOT dress would misalign the vanilla face still sitting in it.
    """
    slots = set(PORTRAIT_MAP.values()) | set(dressed_guest_slots(campaign))
    if os.path.isfile(os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')):
        slots |= set(CH02_CHWINGA_PORTRAIT_SLOT.values())
    vendor = os.path.join(_bust_dir(campaign), 'vendor')
    slots |= {slot for mug, slot, _rc in CH05_VISIT_FACES.values()
              if os.path.isfile(os.path.join(vendor, mug))}
    return sorted(slots)


def inject_portraits(campaign, verbose=True):
    """Overwrite each mapped vanilla portrait slot with our authored bust."""
    bust_dir = _bust_dir(campaign)
    if not os.path.isdir(PORTRAIT_DIR):
        sys.exit('ERROR: decomp portrait dir not found: %s' % PORTRAIT_DIR)

    guests = {u: s for u, s in GUEST_PORTRAIT_MAP.items()
              if s in dressed_guest_slots(campaign)}
    for unit, vanilla in list(PORTRAIT_MAP.items()) + list(guests.items()):
        bust_path = os.path.join(bust_dir, unit + '.png')
        if not os.path.isfile(bust_path):
            sys.exit('ERROR: missing bust for %s: %s' % (unit, bust_path))

        im = Image.open(bust_path)
        portrait_tool._check_indexed(im, bust_path)
        if im.size != (portrait_tool.BUST_W, portrait_tool.BUST_H):
            sys.exit('ERROR: %s is %s, expected %dx%d bust'
                     % (bust_path, im.size, portrait_tool.BUST_W, portrait_tool.BUST_H))

        # Busts are already canonical FE8 facing (screen-left) -- facing is baked
        # at the render stage (ref_to_bust --flip-h, recorded as art.render.flip_h).
        # static_portrait=True: custom busts are non-animated (no mouth flap, no
        # eye-blink) -- aligning per-frame mouth/eye art for custom portraits is
        # infeasible, so we lock them still. See portrait_tool.generate.
        tileset, mouth, chibi, pal_bytes = portrait_tool.generate(im, static_portrait=True)

        base = os.path.join(PORTRAIT_DIR, 'portrait_' + vanilla)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)

        if verbose:
            print('  %-10s -> portrait_%s (tileset/mouth/chibi/palette)' % (unit, vanilla))


def patch_portrait_geometry(campaign, verbose=True):
    """Normalize the mouth/eye window coords of every dressed portrait slot to our
    bust framing, so the engine's mouth-window overwrite lands on our baked mouth
    (not one tile off, which doubles it). See PORTRAIT_GEOMETRY.

    The slot list MUST be `dressed_portrait_slots` -- every slot we overwrite, not just the
    cast. Missing one is silent: the build is green, the scenario passes, and the face is
    quietly corrupted in-game. Read that function's docstring before narrowing this."""
    slots = dressed_portrait_slots(campaign)
    with open(PORTRAIT_DATA_C, encoding='utf-8') as f:
        lines = f.read().split('\n')
    # FaceData tail: `, 0, xMouth, yMouth, xEyes, yEyes, FACE_BLINK_*`. The `, 0,`
    # constant anchors the four geometry fields uniquely on each entry line.
    geom = re.compile(r'(,\s*0,\s*)\d+,\s*\d+,\s*\d+,\s*\d+(,\s*FACE_BLINK)')
    n = 0
    for i, line in enumerate(lines):
        if any('portrait_%s_tileset' % s in line for s in slots):
            new = geom.sub(r'\g<1>%s\2' % PORTRAIT_GEOMETRY, line)
            if new != line:
                lines[i] = new
                n += 1
    if n == 0:
        sys.exit('ERROR: no portrait_data.c entries matched for geometry patch')
    with open(PORTRAIT_DATA_C, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    if verbose:
        print('  normalized %d slot entries to mouth/eye (%s)' % (n, PORTRAIT_GEOMETRY))


# --- Milestone B: unit names ------------------------------------------------------
# Each cast member wears a vanilla character's slot (PORTRAIT_MAP). We overwrite that
# vanilla character's NAME message in texts/texts.txt with our unit's display name, so
# the recompressed gMsgTable carries it. The vanilla name's message index is the
# slot character's `.nameTextId` -- read it from the decomp, never hardcode (the data
# is the source of truth). Names live in YAML; the C/text we emit is just data.

def load_unit(campaign, unit_id):
    """Load a cast member's YAML from pcs/ or npcs/."""
    base = os.path.join(REPO, 'campaigns', campaign)
    for sub in ('pcs', 'npcs'):
        path = os.path.join(base, sub, unit_id + '.yaml')
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                return yaml.safe_load(f)
    sys.exit('ERROR: no YAML for unit %r under %s/{pcs,npcs}' % (unit_id, base))


def display_name(unit):
    """The <=12-char name FE8 shows; fe_name overrides a too-long `name`."""
    name = unit.get('fe_name') or unit.get('name')
    if not name:
        sys.exit('ERROR: unit %r has no name/fe_name' % unit.get('id'))
    name = str(name).strip()
    if len(name) > FE_NAME_MAX:
        sys.exit('ERROR: name %r is %d chars (>%d); add a shorter fe_name'
                 % (name, len(name), FE_NAME_MAX))
    return name


def vanilla_name_text_id(slot):
    """nameTextId of vanilla CHARACTER_<slot>, scanned from data_characters.c."""
    marker = '[CHARACTER_%s - 1]' % slot.upper()
    with open(CHARACTERS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find nameTextId for %s in %s' % (marker, CHARACTERS_C))


GOAL_WINDOW_MAX_CHARS = 12      # vanilla's own widest: 'Defeat enemy' / 'Seize throne'


def goal_window_body(text):
    """A goal-WINDOW string, width-checked against vanilla's budget.

    The on-map objective window does not wrap or clip gracefully: a string past its width
    runs the last glyph off the right border and drops its tail onto the row below (Nicolas
    spotted the severed 'y' of an injected 'Rout the enemy', 14 chars). FE8 never risks it --
    every vanilla goal-window string fits in 12: Survive(7), Defeat boss(11), Defeat enemy(12),
    Seize gate(10), Seize throne(12). Measured across every chapter's `goal.windowTextId`, so
    the budget is the SHIPPED corpus rather than a guess.
    """
    if len(text) > GOAL_WINDOW_MAX_CHARS:
        sys.exit('ERROR: goal-window text %r is %d chars; the window fits %d '
                 '(vanilla\'s widest are "Defeat enemy" / "Seize throne"). It would spill '
                 'its last glyph past the border and wrap the tail underneath.'
                 % (text, len(text), GOAL_WINDOW_MAX_CHARS))
    return name_message_body(text)


def name_message_body(name):
    """Format a name as a terminated FE8 message, matching vanilla's convention.

    FE8 text packs printable bytes two-at-a-time into u16s (see textprocess.py
    text_to_utf8_u16_array). `[X]` is the 0x00 string terminator. If an odd number
    of name bytes precede it, that 0x00 gets paired into the last character's high
    byte instead of standing alone as 0x0000 -- so the in-game decoder never hits
    its terminator and runs away into the next message (the "Huffman corruption"
    that bit the earlier reset). Vanilla pads odd-length names with `[.]` (0x1F,
    absorbed into the last glyph) to keep the byte count even: "Seth[X]" but
    "Franz[.][X]". We do the same.

    Names come straight from YAML, so they may carry unicode punctuation the FE8
    charset can't render (an em-dash garbled the ch02 "Bryn Shander -- West Gate"
    opening card, #22). Normalize through `_fe_dialogue_text` first -- the same
    ASCII-fold `_script_to_message` applies to dialogue -- so the parity count
    below sees the bytes the encoder will actually emit, not the unicode source.
    """
    name = _fe_dialogue_text(name)
    pad = '[.]' if len(name.encode('utf-8')) % 2 == 1 else ''
    return name + pad + '[X]'


def set_message_body(lines, msg_id, body):
    """Replace the content lines of `## MSG_<id>` with `body` (in place). Idempotent:
    matches the header and rewrites whatever non-blank lines follow it."""
    header = '## MSG_%03X' % msg_id
    for i, line in enumerate(lines):
        if line.strip() == header:
            j = i + 1
            while j < len(lines) and lines[j].strip() != '' \
                    and not lines[j].lstrip().startswith('#'):
                j += 1
            lines[i + 1:j] = [body]
            return True
    sys.exit('ERROR: message header %r not found in %s' % (header, TEXTS_TXT))


def _fe_dialogue_text(s):
    """Normalize locked YAML dialogue to the FE8 charset (ASCII punctuation only)."""
    for a, b in (('—', '--'), ('–', '--'), ('…', '...'),
                 ('‘', "'"), ('’', "'"), ('“', '"'), ('”', '"')):
        s = s.replace(a, b)
    return ' '.join(s.split())


def _wrap_fe_lines(text, width=29):
    """Word-wrap dialogue to GBA text lines. Default width matches vanilla's ON-MAP
    messages (MSG_910/911 top out at 29 chars): map speech bubbles auto-size to the
    text, and longer lines overflow the bubble's max width and clip (caught on the
    2026-06-10 scenes capture -- full-screen Text_BG tolerates ~42, bubbles do not).
    A bare '--' never opens a line: the dash glues to the word before it."""
    out, cur = [], ''
    for w in text.split():
        if w == '--' and cur:
            cur += ' --'
            continue
        cand = (cur + ' ' + w) if cur else w
        if len(cand) > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def _term_pad(body):
    """FE8 Huffman terminator-parity (see [[manchego_stars_text_terminator_parity]]):
    the utf8 message packer (textprocess.py) pairs printable bytes two-at-a-time, so a
    printable run with an ODD length makes its last char swallow the FOLLOWING byte --
    and when that byte is the 0x00 terminator the decoder runs past [X] into the next
    message (garbage + bleed-through). Pad with a [.] before [X] so the odd char eats the
    pad instead. The parity that matters is the FINAL run (the printables after the last
    control code), NOT the whole message: a multi-line body whose earlier [LF] runs are
    odd can sum to an even total yet still have an odd final run (Pinky: 16+19+13=48 even,
    final run 13 odd). No-op when the final run is already even."""
    if not body.endswith('[X]'):
        return body
    inner = body[:-3]                       # strip the [X] terminator
    last_close = inner.rfind(']')           # final run = text after the last control tag
    final_run = (inner[last_close + 1:] if last_close != -1 else inner).replace('\n', '')
    if len(final_run) % 2:
        body = inner + '[.][X]'
    return body


def _script_to_message(script, staging, width=29, face_budget=4, preload=None,
                       trailing=None):
    """Render a chapter-YAML cutscene `script:` block as an FE8 message body.

    Mirrors the vanilla shape (cf. MSG_910/911): faces are loaded lazily at a
    speaker's first turn (so a boss can "step out" mid-scene), [LF] joins the two
    lines of a page, [A][LF] breaks pages (2 visible lines per A-press).

    Consecutive turns by the SAME speaker are coalesced into one [OpenX] block
    with the turn boundary as a page break. This is load-bearing, not cosmetic:
    the map-bubble width measure (GetStrTalkLen, scene.c) does NOT stop at [A] --
    it adds 12px and keeps measuring until the next speaker's printable text, and
    only [LF]/[CR] reset the line accumulator. An [A][OpenX-same-face] boundary
    without [LF] therefore merges both turns into one measured "line"; widths
    over 29 tiles make PutTalkBubble's right-side branch compute x = 29 - width
    < 0 (no clamp, unlike the left branch) and the bubble wraps the tilemap --
    the offscreen/empty-bubble bug of the 2026-06-10 scenes captures. Vanilla
    never ships an [A] that isn't terminal or [LF]-followed; now neither do we.

    FACE BUDGET (the 4-slot fix, #21 Beat 1): only FACE_SLOT_COUNT = 4 faces can
    be loaded at once (the gFaces pool; include/face.h). Vanilla .h scenes cap at
    <=4 by hand, but our big set pieces (the Northlook roll-call) have ~10
    speakers in one message, so this tracks PODIUMS (screen positions), not
    speakers, as the budget. `live` maps an [OpenX] tag -> the speaker whose face
    sits there; `lru` orders podiums least-recently-used first. When a podium is
    re-used by a different speaker we emit `[OpenX][ClearFace]` (scene.c: fades
    out faces[activePosition] and frees its gFaces slot, ~16-frame fade -> reads
    as pacing between speakers); when all four are full we evict the LRU podium.
    A rotating spotlight (many speakers staged to ONE podium) thus shows one face
    at a time while other speakers stay anchored elsewhere. The temporary lock on
    [ClearFace] means the fade-out frees its slot BEFORE the following [LoadFace]
    runs, so the pool never momentarily overflows. (With <=4 distinct podiums this
    is byte-for-byte the old lazy-load behaviour -- the prologue is unaffected.)

    A `staging` value of (open_tag, None) is a FACELESS speaker (stage business):
    its text prints in a box with no [LoadFace], at a podium that should be left
    unoccupied so no loaded face mouth-moves under it.

    `preload` is a list of (open_tag, [FID_x]) faces shown BEFORE the dialogue --
    silent listeners (e.g. the party watching Hlin's monologue, or Hruna standing
    across from RBG). They seed the live map so the speaker(s) talk TO a populated
    room instead of an empty one; keep preload podiums distinct from the beat's
    speaker podiums, and the total (preload + concurrent speakers) within the
    4-face budget so no listener is evicted.

    `location_card` / `fade_to_black` / `beat_break` entries are staged by the
    event script (or split into separate messages), not the message body, and are
    skipped here. `width` is the wrap width (29 = map speech bubble; ~42 for a
    full-screen scenic BG -- see _wrap_fe_lines).

    `trailing` is a raw text-code string appended just before the [X] terminator --
    e.g. '[OpenMidLeft][ClearFace]' to fade ONLY that podium's face at the beat's
    end (scene.c: StartFaceFadeOut on faces[activeFaceSlot]), leaving the others up.
    The one low-level face control the podium auto-manager doesn't infer: a speaker
    who exits mid-scene while a co-speaker holds (the ch03 Pinky-scout -> RBG waits).
    """
    blocks = []   # (speaker, [page, ...]); page = 'line1[LF]\nline2'
    for entry in script:
        (speaker, text), = entry.items()
        if speaker in ('location_card', 'fade_to_black', 'beat_break'):
            continue
        lines = _wrap_fe_lines(_fe_dialogue_text(text), width)
        pages = ['[LF]\n'.join(lines[p:p + 2]) for p in range(0, len(lines), 2)]
        if blocks and blocks[-1][0] == speaker:
            blocks[-1][1].extend(pages)
        else:
            blocks.append((speaker, pages))
    parts = []
    live = {}   # [OpenX] tag -> speaker currently holding that podium's face
    lru = []    # [OpenX] tags, least-recently-used first
    for pos, fid in (preload or []):          # silent listeners, loaded first
        parts.append('%s[LoadFace]%s' % (pos, fid))
        live[pos] = '\x00listener'            # sentinel: never matches a real speaker
        lru.append(pos)
    for speaker, pages in blocks:
        open_tag, fid_tag = staging[speaker]
        if fid_tag is None:           # faceless stage business -- no face, no slot
            # Emit NO [OpenX] code: those are portrait POSITION anchors (textdefs.txt
            # [OpenMidLeft]=9 ... ); opening one without a [LoadFace] anchors the text
            # window to an absent portrait's mouth and the box renders as a cramped,
            # mis-placed sliver (the "Marty leans in..." narration bug, 2026-06-17).
            # Plain text shows in the default full-width box, which is what narration wants.
            parts.append('[A][LF]\n'.join(pages) + '[A]')
            continue
        body = open_tag + '[A][LF]\n'.join(pages) + '[A]'
        if live.get(open_tag) == speaker:           # already on screen here
            lru.remove(open_tag)
            lru.append(open_tag)
        else:
            if open_tag in live:                    # podium held by someone else
                parts.append(open_tag + '[ClearFace]')
                del live[open_tag]
                lru.remove(open_tag)
            while len(live) >= face_budget:         # all podiums full -> evict LRU
                old = lru.pop(0)
                parts.append(old + '[ClearFace]')
                del live[old]
            parts.append('%s[LoadFace]%s' % (open_tag, fid_tag))
            live[open_tag] = speaker
            lru.append(open_tag)
        parts.append(body)
    return '\n'.join(parts) + (trailing or '') + '[X]'


def _beat_is_narration(beat):
    """True if every entry in a scenic beat is faceless `narration` stage-business."""
    return bool(beat) and all('narration' in e for e in beat)


def _beat_is_faceless(beat, fid):
    """True if a scenic beat has NO on-screen face -- every speaker resolves faceless (fid k is None).
    A superset of _beat_is_narration (which keys on the literal 'narration' speaker): also catches a
    named-but-portraitless speaker (e.g. the ch03 kobold-brute, no mug art). Such a beat CANNOT ride
    a map talk bubble on-map -- PutTalkBubble anchors to a speaking unit, and an AFEV event script has
    none, so the bubble renders off the tilemap -- it must use the opaque AUTO-CENTERED box
    (SOLOTEXTBOXSTART), which needs no anchor. (Over a BG the full-screen window sidesteps this, which
    is why the opening/ending don't hit it; the mid-map RBG-execution beat, on-map, does.)"""
    keys = [next(iter(e)) for e in beat
            if next(iter(e)) not in ('location_card', 'beat_break')]
    return bool(keys) and all(fid(k) is None for k in keys)


def _scenic_beat_calls(msgs, beats, labels):
    """One event-script text call per scenic beat. A beat that is ALL faceless
    `narration` rides an opaque, auto-centered SOLOTEXTBOXSTART box (gProcScr_BoxDialogue,
    helpbox.c) so the aside is never boxless over the scene art (#58); EVT_SLOT_B =
    0x00FF00FF feeds x=y=0xFF -> auto-center (dialogue-box config flag 0x100, sub_800E31C).
    A beat with any faced speaker rides the normal talk window via Text() (TEXTSTART)."""
    out = []
    for msg, beat, lbl in zip(msgs, beats, labels):
        if _beat_is_narration(beat):
            out.append('    SVAL(EVT_SLOT_B, 0xFF00FF) /* auto-center the opaque solo box (#58) */\n'
                       '    SOLOTEXTBOXSTART\n'
                       '    TEXTSHOW(0x%X) /* %s */\n    TEXTEND\n    REMA\n' % (msg, lbl))
        else:
            out.append('    Text(0x%X) /* %s */\n' % (msg, lbl))
    return ''.join(out)


def _fid_tag(slot):
    """textdefs.txt face-tag for a vanilla character slot (CamelCase, irregulars mapped)."""
    special = {'ONEILL': 'ONeill', 'VILLAGER_WOMAN': 'VillagerWoman'}
    return '[FID_%s]' % special.get(slot, slot.title())


def dev_placeholder_scene():
    """Event-script tail for an unbuilt chapter boundary (see DEV_PLACEHOLDER_MSG).

    Drop this in place of an `MNC2(next)` whose next chapter isn't hosted yet: the
    caller has just faded to black (FADI), so this reveals the campfire BG, shows
    RBG's "still under construction" cheese-pun line, then returns to the title
    screen (MNTS = EvtBackToTitle -> GAME_ACTION_EVENT_RETURN, eventscr.c). No chapter
    is loaded, so the player never lands on a leftover vanilla map. The matching
    message body is set by dev_placeholder_message()."""
    return (
        '    REMOVEPORTRAITS\n'
        '    BACG(BG_FIREPLACE) /* dev placeholder: RBG by the campfire */\n'
        '    FADU(16)\n'
        '    Text(0x%X) /* RBG: "still under construction" cheese pun */\n'
        '    FADI(16)\n'
        '    MNTS(0x0) /* next chapter not built yet -> back to title */\n'
        % DEV_PLACEHOLDER_MSG)


def dev_placeholder_message():
    """The RBG dev-placeholder message body (one speaker, scenic wrap)."""
    slot = PORTRAIT_MAP[DEV_PLACEHOLDER_SPEAKER]
    return _script_to_message(
        [{DEV_PLACEHOLDER_SPEAKER: DEV_PLACEHOLDER_LINE}],
        {DEV_PLACEHOLDER_SPEAKER: ('[OpenMidLeft]', _fid_tag(slot))},
        width=42)


def inject_names(campaign, verbose=True):
    """Write each cast member's display name into its vanilla slot's name message."""
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        name = display_name(unit)
        text_id = vanilla_name_text_id(slot)
        set_message_body(lines, text_id, name_message_body(name))
        if verbose:
            print('  %-10s -> MSG_%03X (was %s): %s' % (unit_id, text_id, slot, name))
    for _pid, (unit_id, slot, _portrait_id, name) in sorted(RAW_PID_PORTRAITS.items()):
        text_id = vanilla_name_text_id(slot)
        set_message_body(lines, text_id, name_message_body(name))
        if verbose:
            print('  %-10s -> MSG_%03X (was %s): %s' % (unit_id, text_id, slot, name))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def item_name_text_id(item_enum):
    """nameTextId of a vanilla item, scanned from data_items.c. FE8 stores one name
    message per item id (gItemData[].nameTextId), so renaming it retitles every copy
    of that item in-game -- read the id from the decomp, never hardcode."""
    marker = '[%s] = {' % item_enum
    with open(ITEMS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find nameTextId for %s in %s' % (item_enum, ITEMS_C))


def item_icon_id(item_enum):
    """gItemData[item].iconId, scanned from data_items.c."""
    marker = '[%s] = {' % item_enum
    with open(ITEMS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.iconId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find iconId for %s in %s' % (item_enum, ITEMS_C))


def item_icon_png_path(icon_id):
    """The graphics/item_icon/*.png build-source file an iconId resolves to. Item icons
    are 16x16 4bpp tiles concatenated in data/data_item_icon.s in iconId order
    (item_icon_tiles); the Nth .incbin (0-based) is iconId N, and the decomp builds each
    .4bpp from a same-named .png (`%.4bpp: %.png`). Read it, never hardcode the name."""
    s = os.path.join(DECOMP, 'data', 'data_item_icon.s')
    incbins = re.findall(r'\.incbin\s+"(graphics/item_icon/[^"]+)\.4bpp"',
                         open(s, encoding='utf-8').read())
    if icon_id >= len(incbins):
        sys.exit('ERROR: iconId %#x past %d item icons in %s' % (icon_id, len(incbins), s))
    return incbins[icon_id] + '.png'


def inject_item_icons(campaign, verbose=True):
    """Swap a vanilla item's 16x16 icon for a campaign asset from campaign.yaml
    `item_icons:` (ITEM enum -> item_icons/<name>.png). Overwrites the item's tracked
    .png source (gbagfx makes the .4bpp at build). FE8 keeps one icon per item id, so
    every copy shows the new art (cf. inject_item_names for the name)."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        icons = (yaml.safe_load(f) or {}).get('item_icons') or {}
    if not icons:
        if verbose:
            print('  (no item_icons declared)')
        return
    from PIL import Image
    for item_enum, asset in icons.items():
        src = os.path.join(REPO, 'campaigns', campaign, 'item_icons', asset + '.png')
        if not os.path.isfile(src):
            sys.exit('ERROR: item_icon asset not found: %s' % src)
        im = Image.open(src)
        if im.mode != 'P' or im.size != (16, 16):
            sys.exit('ERROR: %s must be a 16x16 indexed (mode P) PNG; got %s %s'
                     % (src, im.mode, im.size))
        rel = item_icon_png_path(item_icon_id(item_enum))
        shutil.copyfile(src, os.path.join(DECOMP, rel))
        if verbose:
            print('  %-18s -> %s' % (item_enum, rel))


def _bgr555(hexstr):
    """'#rrggbb' -> a 15-bit BGR555 halfword (FE8 .agbpal / GBA palette format)."""
    h = hexstr.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def _item_icon_pal2_bytes(colors):
    """16 '#rrggbb' colors -> a 32-byte BGR555 blob (one 16-colour item-icon palette bank)."""
    if len(colors) != 16:
        sys.exit('ERROR: item_icon_pal2.palette must have exactly 16 colors (got %d)' % len(colors))
    return b''.join(struct.pack('<H', _bgr555(c)) for c in colors)


def _append_item_icon_pal2(raw, colors):
    """Append the custom icon palette after FE8's two vanilla banks, without altering either."""
    if len(raw) < 64:
        sys.exit('ERROR: item_icon_palette.agbpal has %d bytes; expected two vanilla banks' % len(raw))
    out = bytearray(raw)
    if len(out) < 96:
        out.extend(b'\x00' * (96 - len(out)))
    out[64:96] = _item_icon_pal2_bytes(colors)
    return out


def _pal2_icon_ids(campaign):
    """The iconIds (gItemData.iconId) of the campaign's item_icon_pal2.icons, sorted."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        pal2 = (yaml.safe_load(f) or {}).get('item_icon_pal2') or {}
    return sorted(item_icon_id(e) for e in (pal2.get('icons') or []))


def _ms_pal2_iconids_asm(ids):
    """gMSPal2IconIds[] -- iconIds the DrawIcon hook routes from BG bank 4 to reserved bank 15.
    The 0xFFFF terminator is outside the valid icon-id range."""
    lines = ['', '/* Manchego Stars item icons that draw from custom palette 2 (#23). */',
             '\t.align 2, 0', '\t.global gMSPal2IconIds', 'gMSPal2IconIds:']
    lines += ['\t.hword %d' % i for i in ids]
    lines.append('\t.hword 0xFFFF')
    return '\n'.join(lines)


def inject_item_icon_pal2(campaign, verbose=True):
    """Wire custom-coloured item icons (#23) through an additive third source palette.

    The two vanilla banks stay byte-for-byte intact. This appends item_icon_pal2.palette and emits
    gMSPal2IconIds[]; the generic DrawIcon hook routes those standard item icons from BG bank 4 to
    the dedicated custom bank 15. No-op when no item_icon_pal2 is declared.
    """
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        pal2 = (yaml.safe_load(f) or {}).get('item_icon_pal2') or {}
    if not pal2:
        if verbose:
            print('  (no item_icon_pal2 declared)')
        return
    palpath = os.path.join(DECOMP, 'graphics', 'item_icon', 'item_icon_palette.agbpal')
    with open(palpath, 'rb') as f:
        raw = bytearray(f.read())
    with open(palpath, 'wb') as f:
        f.write(_append_item_icon_pal2(raw, pal2['palette']))
    ids = _pal2_icon_ids(campaign)
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write(_ms_pal2_iconids_asm(ids) + '\n')
    if verbose:
        print('  custom palette appended; gMSPal2IconIds = %s' % ids)


def inject_item_names(campaign, verbose=True):
    """Rename vanilla items globally from campaign.yaml `item_names:` (ITEM enum ->
    display name). FE8 keeps a single name per item id, so a reflavored consumable
    reads the same for the whole party (cf. the cast's per-unit flavor names are
    documentation only -- the engine can't differ them)."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        renames = (yaml.safe_load(f) or {}).get('item_names') or {}
    if not renames:
        if verbose:
            print('  (no item_names declared)')
        return
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for item_enum, name in renames.items():
        text_id = item_name_text_id(item_enum)
        set_message_body(lines, text_id, name_message_body(str(name)))
        if verbose:
            print('  %-18s -> MSG_%03X: %s' % (item_enum, text_id, name))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


DATA_BANIM_S = os.path.join(DECOMP, 'data', 'data_banim.s')


def _gba_lz77_stored(data):
    """A GBA LZ77 container in stored (literal-only) form: header 0x10|size<<8,
    then a 0x00 flag byte + 8 literal bytes per block. Always valid input for
    LZ77UnCompWram; the ~12% size tax on these tiny efx assets beats vendoring
    a real compressor."""
    out = bytearray(struct.pack('<I', 0x10 | (len(data) << 8)))
    for i in range(0, len(data), 8):
        chunk = data[i:i + 8]
        out.append(0)
        out += chunk + b'\0' * (8 - len(chunk))
    return bytes(out)


def _crit_flourish_bins(png_path):
    """battle_anims/d20-crit.png (RGBA, tile-multiple dims, <=15 opaque colors) ->
    (img_lz, pal_raw, tsa_lz) for the banim SpellFx BG1 layer: a 4bpp tile sheet
    (tile 0 = blank), a 16-color palette (index 0 = the transparent slot), and a
    30x20 TSA of raw tile indices (EfxTmCpyBG adds the palette/charblock bits)
    centering the art on the upper screen."""
    from PIL import Image
    im = Image.open(png_path).convert('RGBA')
    if im.width % 8 or im.height % 8 or im.width > 240 or im.height > 160:
        sys.exit('ERROR: %s must be 8px-multiple dims within the 240x160 screen'
                 % png_path)
    tw, th = im.width // 8, im.height // 8
    # SpellFx_RegisterBgGfx decompresses into gSpellAnimBgfx (0x1D00 B = 232
    # tiles, banim-ekrbattle.c) -- overflow corrupts adjacent banim overlay state
    if tw * th + 1 > 232:
        sys.exit('ERROR: %s is %d tiles + 1 blank; the SpellFx gfx buffer holds '
                 '232 (gSpellAnimBgfx, 0x1D00 B)' % (png_path, tw * th))
    px = im.load()
    colors = []

    def cidx(p):
        if p[3] < 128:
            return 0
        if p[:3] not in colors:
            colors.append(p[:3])
            if len(colors) > 15:
                sys.exit('ERROR: %s exceeds 15 opaque colors; the 4bpp sheet '
                         'caps there (index 0 is the transparent slot)' % png_path)
        return colors.index(p[:3]) + 1

    tiles = [bytes(32)]                       # tile 0 = blank (the empty screen)
    tsa = [[0] * 30 for _ in range(20)]
    ox, oy = (30 - tw) // 2, 3                # centered, upper third
    for ty in range(th):
        for tx in range(tw):
            data = bytearray()
            for row in range(8):
                for b in range(4):
                    left = cidx(px[tx * 8 + b * 2, ty * 8 + row])
                    right = cidx(px[tx * 8 + b * 2 + 1, ty * 8 + row])
                    data.append(left | (right << 4))
            tiles.append(bytes(data))
            tsa[oy + ty][ox + tx] = len(tiles) - 1
    pal = bytearray(2)                        # index 0 stays black/transparent
    for r, g, b in colors:
        pal += struct.pack('<H', (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    pal += b'\0' * (32 - len(pal))
    img = b''.join(tiles)
    tsa_bytes = b''.join(struct.pack('<H', t) for row in tsa for t in row)
    return _gba_lz77_stored(img), bytes(pal), _gba_lz77_stored(tsa_bytes)


def inject_crit_flourish(campaign, verbose=True):
    """The cosmetic nat-20 crit flourish (#11): the ENGINE half is a campaign-
    agnostic hook (engine_hooks._inject_crit_d20_flourish -- a d20 pops on the
    SpellFx layer when the vanilla crit flash tears down); the ART comes from the
    campaign (battle_anims/d20-crit.png). No asset -> neither half applies and
    combat stays pure vanilla."""
    src = os.path.join(REPO, 'campaigns', campaign, 'battle_anims', 'd20-crit.png')
    if not os.path.isfile(src):
        if verbose:
            print('  no battle_anims/d20-crit.png -- flourish skipped (vanilla crits)')
        return
    img, pal, tsa = _crit_flourish_bins(src)
    for stem, data in (('msd20crit_img', img), ('msd20crit_pal', pal),
                       ('msd20crit_tsa', tsa)):
        with open(os.path.join(DECOMP, 'graphics', 'banim', stem + '.bin'), 'wb') as f:
            f.write(data)
    with open(DATA_BANIM_S, encoding='utf-8') as f:
        already = '.global Img_MsD20Crit' in f.read()
    if already:
        # idempotent like the C-side 'MS #11' guard: a second run in one process
        # must not append duplicate labels (assembler: symbol already defined)
        engine_hooks._inject_crit_d20_flourish()
        return
    with open(DATA_BANIM_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars #11: nat-20 crit flourish (campaign asset) */']
            + sum(([  '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
                      '\t.incbin "graphics/banim/%s.bin"' % stem]
                   for label, stem in (('Img_MsD20Crit', 'msd20crit_img'),
                                       ('Pal_MsD20Crit', 'msd20crit_pal'),
                                       ('Tsa_MsD20Crit', 'msd20crit_tsa'))), []))
            + '\n')
    engine_hooks._inject_crit_d20_flourish()
    if verbose:
        print('  d20 flourish armed: %d B gfx + %d B tsa on the crit-flash teardown'
              % (len(img), len(tsa)))


# --- Milestone B: character stats / class -----------------------------------------
# Write each cast unit's vanilla-class identity into its portrait slot's
# gCharacterData[] entry: defaultClass, affinity (Anima, cosmetic), baseLevel --
# and the MECHANICAL character layer inherited from a class-matched VANILLA DONOR
# (STAT_DONOR / GROWTH_DONOR): personal bases = (YAML fe_stats - class base) + the
# donor's personal bases, growths copied verbatim from the growth donor, weapon
# ranks from the rank donor. So an FE-strict unit (fe_stats == class base, the
# default) lands exactly on its donor's statline -- vanilla character data under a
# new identity, not "naked class" frailty (decisions.md: even character-level
# mechanical data is vanilla; ours is the donor CHOICE + cosmetics + levels).
# Any deliberate YAML divergence still stacks on top so displayed stats ==
# fe_stats. Gender IS driven from YAML (_set_gender rewrites .attributes CA_FEMALE);
# only portraitId and pSupportData are left as the vanilla slot's -- supports are a
# later YAML-driven pass.

def _set_field(block, field, value, path, marker):
    """Replace `.field = ...,` within `block`. Errors if the field isn't present."""
    pat = re.compile(r'(\.' + field + r'\s*=\s*)[^,\n]*(,)')
    new, n = pat.subn(lambda m: m.group(1) + str(value) + m.group(2), block, count=1)
    if n == 0:
        sys.exit('ERROR: field .%s not found in %s entry %s' % (field, path, marker))
    return new


def vanilla_decomp_text(relpath):
    """Committed (HEAD) text of a decomp source file -- immune to the working-tree patching
    the build applies to PATCHED_DECOMP_FILES (e.g. data_characters.c portrait slots get
    overwritten, data_classes.c gets enemy-class clones). Anything that wants the *vanilla*
    value (donor stats, class bases, the difficulty engine) must read through here, not the
    mutable working tree. relpath is under fireemblem8u/, e.g. 'src/data_characters.c'."""
    # Strip inherited git env so `git -C DECOMP` discovers the submodule's own gitdir.
    # Git sets GIT_DIR (etc.) when this runs inside a commit hook, and an explicit
    # GIT_DIR overrides the -C discovery -- so `show HEAD:...` resolves against the
    # superproject and fails (128). Bit us committing from a content/pipeline worktree,
    # whose submodule gitdir is separate from the superproject's.
    env = {k: v for k, v in os.environ.items()
           if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX',
                        'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_NAMESPACE',
                        'GIT_ALTERNATE_OBJECT_DIRECTORIES')}
    return subprocess.check_output(['git', '-C', DECOMP, 'show', 'HEAD:' + relpath],
                                   encoding='utf-8', env=env)


def class_base_stats(class_enum, classes_text=None):
    """Read a class's base stats, keyed by CharacterData field name (baseHP, basePow, ...).
    Luck is character-only, so baseLck defaults to 0. `classes_text` overrides the source
    (pass vanilla_decomp_text('src/data_classes.c') to be immune to reskin patching)."""
    text = classes_text if classes_text is not None else open(CLASSES_C, encoding='utf-8').read()
    s, e = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    block = text[s:e]
    out = {'baseLck': 0}
    for cf in CLASS_BASE_FIELDS:
        m = re.search(r'\.' + cf + r'\s*=\s*(-?\d+)', block)
        out[cf] = int(m.group(1)) if m else 0
    return out


def class_enum_for(unit):
    raw = unit.get('fe_stats', {}).get('class')
    if not raw:
        return None
    base = re.sub(r'\s*\(.*?\)', '', str(raw)).strip()
    if base not in CLASS_MAP:
        sys.exit('ERROR: unit %r class %r not in CLASS_MAP' % (unit.get('id'), base))
    return CLASS_MAP[base]


def deploy_class_for(unit):
    """The class enum a unit is DEPLOYED as (its `defaultClass` + UnitDef `classIndex`).

    Every cast member deploys as their plain vanilla class. Custom battle anims no longer
    need a clone class: they ride the per-character `_u25` table (#65 M-B, see
    inject_battle_anims + the _patch_banim_character_unique engine hook)."""
    return class_enum_for(unit)


def donor_growths_and_ranks(vanilla_text, donor_char):
    """Read a stat-donor unit's growths + baseRanks initializer from VANILLA
    data_characters.c text (so it's unaffected by patches we apply this run)."""
    s, e = _find_brace_block(vanilla_text, '[%s - 1]' % donor_char, CHARACTERS_C)
    block = vanilla_text[s:e]
    growths = {}
    for gf in GROWTH_FIELDS:
        m = re.search(r'\.' + gf + r'\s*=\s*(-?\d+)', block)
        growths[gf] = int(m.group(1)) if m else 0
    rm = re.search(r'\.baseRanks\s*=\s*(\{.*?\})', block, re.DOTALL)
    ranks = re.sub(r'\s+', ' ', rm.group(1)).strip() if rm else '{}'
    return growths, ranks


# A donor's personal base layer = the displayed-stat fields keyed as gCharacterData
# stores them (base* deltas the engine adds on top of the class base). Luck is
# character-only, so a missing field reads 0. baseMov is class-only -> excluded.
BASE_FIELDS = ('baseHP', 'basePow', 'baseSkl', 'baseSpd', 'baseDef',
               'baseRes', 'baseLck', 'baseCon')


def donor_base_stats(vanilla_text, donor_char):
    """Read a stat-donor unit's personal BASE stats from VANILLA data_characters.c
    text. These are the personal line a class-matched canonical unit carries on top
    of its class base -- inheriting them lifts our cast off "naked class" frailty to
    vanilla parity. Mirrors donor_growths_and_ranks (same snapshot discipline)."""
    s, e = _find_brace_block(vanilla_text, '[%s - 1]' % donor_char, CHARACTERS_C)
    block = vanilla_text[s:e]
    bases = {}
    for bf in BASE_FIELDS:
        m = re.search(r'\.' + bf + r'\s*=\s*(-?\d+)', block)
        bases[bf] = int(m.group(1)) if m else 0
    return bases


def personal_base_deltas(fe_stats, class_base, donor_base):
    """The personal-base layer to patch into a cast slot's gCharacterData, keyed by base
    field. FE8 shows class base + this layer, so each field is (authored fe_stat - class
    base) + the donor's personal base: an FE-strict unit (fe_stats == class base) lands on
    its donor's line, and any deliberate authored divergence stacks on top. MOV is class-
    only (no STAT_FIELD entry) and is skipped."""
    out = {}
    for fe, value in fe_stats.items():
        field = STAT_FIELD.get(fe)
        if field is None:
            continue
        out[field] = int(value) - class_base.get(field, 0) + donor_base.get(field, 0)
    return out


def _set_gender(block, female):
    """Set the CA_FEMALE attribute. Replaces .attributes if present; if absent,
    inserts it only when female (absent already means 0 == male)."""
    val = 'CA_FEMALE' if female else '0'
    pat = re.compile(r'(\.attributes\s*=\s*)[^,\n]*(,)')
    new, n = pat.subn(lambda m: m.group(1) + val + m.group(2), block, count=1)
    if n:
        return new
    if not female:
        return block  # no attributes field => already 0 => male; nothing to do
    idx = block.rfind('}')
    return block[:idx] + '    .attributes = CA_FEMALE,\n    ' + block[idx:]


def patch_character_data(campaign, verbose=True):
    """Inject class + base stats into each cast slot's gCharacterData entry."""
    with open(CHARACTERS_C, encoding='utf-8') as f:
        text = f.read()
    # Donor bases/growths/ranks are read from the committed (HEAD) source, NOT `text`:
    # several donors (Gilliam, Neimi, Moulder, Vanessa) ride portrait slots this very pass
    # overwrites, so a working-tree read could see an already-patched donor.
    vanilla = vanilla_decomp_text('src/data_characters.c')

    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            if verbose:
                print('  %-10s -> %-8s: no class yet (name only)' % (unit_id, slot))
            continue

        st = unit['fe_stats']
        cbase = class_base_stats(class_enum)
        # MOV is class-only; we can't set it per-character -- just sanity-check it.
        if 'MOV' in st and int(st['MOV']) != cbase['baseMov']:
            print('  WARN %s: MOV %s != class %s base MOV %d (MOV is class-fixed)'
                  % (unit_id, st['MOV'], class_enum, cbase['baseMov']))

        marker = '[CHARACTER_%s - 1]' % slot.upper()
        s, e = _find_brace_block(text, marker, CHARACTERS_C)
        block = text[s:e]
        block = _set_field(block, 'defaultClass', deploy_class_for(unit), CHARACTERS_C, marker)
        block = _set_field(block, 'affinity', 'UNIT_AFFIN_ANIMA', CHARACTERS_C, marker)
        block = _set_field(block, 'baseLevel', int(st.get('level', 1)), CHARACTERS_C, marker)

        # Personal base layer = (authored - class) + the donor's personal line, so the
        # cast lands at vanilla parity instead of "naked class" (donor-base inheritance, #45).
        dbase = donor_base_stats(vanilla, BASE_DONOR[unit_id])
        deltas = personal_base_deltas(st, cbase, dbase)
        for field, delta in deltas.items():
            block = _set_field(block, field, delta, CHARACTERS_C, marker)

        # Growths from the growth donor, weapon ranks from the rank donor (usually the same
        # unit; the shamans split -- Mees grows on Ewan but keeps Knoll's Dark rank). Both
        # read from VANILLA so the unit levels and fights like a real FE unit of its class.
        growths, _ = donor_growths_and_ranks(vanilla, GROWTH_DONOR[unit_id])
        _, ranks = donor_growths_and_ranks(vanilla, STAT_DONOR[unit_id])
        for gf, gv in growths.items():
            block = _set_field(block, gf, gv, CHARACTERS_C, marker)
        block, n = re.subn(r'(\.baseRanks\s*=\s*)\{.*?\}',
                           lambda m: m.group(1) + ranks, block, count=1, flags=re.DOTALL)
        if n == 0:
            sys.exit('ERROR: .baseRanks not found in %s %s' % (CHARACTERS_C, marker))

        # Gender flag (CA_FEMALE): drive from YAML (default male). Some vanilla entries
        # omit .attributes (absent == 0 == male), so set tolerantly. Clears CA_FEMALE
        # leaking from the slot; custom gendered sprites are a separate art pass.
        female = str(unit.get('gender', 'male')).lower() == 'female'
        block = _set_gender(block, female)

        text = text[:s] + block + text[e:]
        if verbose:
            shown = ' '.join('%s%d' % (k, int(st[k])) for k in
                             ('HP', 'STR', 'MAG', 'SKL', 'SPD', 'DEF', 'RES', 'LCK', 'CON')
                             if k in st)
            nz = {k: v for k, v in deltas.items() if v != 0}
            tag = '' if not nz else '  (deltas %s)' % nz
            short = lambda d: d.replace('CHARACTER_', '')
            donors = 'base<-%s grow<-%s rank<-%s' % (
                short(BASE_DONOR[unit_id]), short(GROWTH_DONOR[unit_id]),
                short(STAT_DONOR[unit_id]))
            print('  %-10s -> %-8s: %s L%s  %s  %s%s%s'
                  % (unit_id, slot, class_enum, st.get('level', 1), shown,
                     donors, '  [F]' if female else '', tag))

    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(text)


def raw_pid_portrait_data(text, campaign):
    """Bind named raw-pid enemies to their authored identity and personal stat line.

    Raw 0xB0-range CharacterData gaps carry only a generic miniPortrait and omit portraitId,
    while their nameTextId points at the generic "Monster" message. Repoint the name to the
    dressed slot's own message and insert the full portrait id after defaultClass (or replace
    it on a repeat run), while preserving the generic miniPortrait field. Named bosses also
    need their YAML `personal` bases written here: FE8 adds those CharacterData values to the
    deployed class bases, exactly as vanilla Ch5 does for Saar.
    """
    for pid, (_unit_id, slot, portrait_id, _name) in sorted(RAW_PID_PORTRAITS.items()):
        marker = '[%s - 1]' % pid.lower()
        start, end = _find_brace_block(text, marker, CHARACTERS_C)
        block = text[start:end]
        block = _set_field(block, 'nameTextId', '0x%X' % vanilla_name_text_id(slot),
                           CHARACTERS_C, marker)
        if re.search(r'\.portraitId\s*=', block):
            block = _set_field(block, 'portraitId', '0x%X' % portrait_id,
                               CHARACTERS_C, marker)
        else:
            pat = re.compile(r'(?m)^(\s*\.defaultClass\s*=\s*[^,\n]+,\s*\n)')
            block, count = pat.subn(
                lambda m: m.group(1) + '        .portraitId = 0x%X,\n' % portrait_id,
                block, count=1)
            if count != 1:
                sys.exit('ERROR: .defaultClass insertion point not found in %s entry %s'
                         % (CHARACTERS_C, marker))

        personal_source = RAW_PID_PERSONAL_SOURCES.get(pid)
        if personal_source:
            chapter_yaml, unit_id = personal_source
            chapter = _load_chapter_yaml(campaign, chapter_yaml)
            unit = next((enemy for enemy in chapter['enemy_units']
                         if enemy['id'] == unit_id), None)
            if unit is None or 'personal' not in unit:
                sys.exit('ERROR: raw pid %s personal source %s/%s is missing'
                         % (pid, chapter_yaml, unit_id))
            for field in BASE_FIELDS:
                block = _set_field(block, field, int(unit['personal'].get(field, 0)),
                                   CHARACTERS_C, marker)
        text = text[:start] + block + text[end:]
    return text


def patch_raw_pid_portraits(campaign, verbose=True):
    """Write raw_pid_portrait_data() to the decomp CharacterData table."""
    with open(CHARACTERS_C, encoding='utf-8') as f:
        text = f.read()
    text = raw_pid_portrait_data(text, campaign)
    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(text)
    if verbose:
        print('  %d raw-pid identity binding(s) patched' % len(RAW_PID_PORTRAITS))


# --- Milestone B step 3: test-chapter spawn ---------------------------------------
# First in-engine confirmation that names + portraits + classes + stats land together.
# We keep vanilla Ch1's MAP but strip its scripting to a bare sandbox: the original
# beginning scene choreographs specific vanilla units (scripted Breguet fight, forced
# moves, MoveUnitS2ToLeader) and was deleting our cast mid-cutscene -> instant lord-
# death game over. Instead we:
#   * rewrite the player roster (UnitDef_Event_Ch1Ally) to our classed cast,
#   * replace the beginning scene with a minimal "load the cast, hand over control",
#   * empty every per-chapter event list (turn/character/location/misc/tutorial) so
#     nothing references removed units or fires a win/lose condition,
#   * cut the boot attract reel + redirect prologue->Ch1 so a fresh boot lands on the
#     title and New Game drops straight onto the map (dev loop).
# Result: New Game -> Ch1 map with the 8 cast, no cutscene, no game over -- a
# combat-ready sandbox (the vanilla foes stay, reskinned; no objective -- reset when
# done; battle-anim capture fires on them). Each cast unit rides its
# PORTRAIT_MAP slot's CHARACTER_ id, so its injected name/portrait/class/stats show.
# redaCount=0 places a unit statically at xPosition/yPosition (eventscr.c sub_800F8A8).
# All edits are restorable build artifacts (PATCHED_DECOMP_FILES). Authored chapters
# (real maps/events/objectives from YAML) supersede this whole step.

# Stock starting loadout per class enum (vanilla ITEM_ ids; see constants/items.h).
CLASS_LOADOUT = {
    'CLASS_PIRATE':         ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE', 'ITEM_VULNERARY'],
    'CLASS_SHAMAN':         ['ITEM_DARK_FLUX', 'ITEM_VULNERARY'],
    'CLASS_ARCHER':         ['ITEM_BOW_IRON', 'ITEM_VULNERARY'],
    'CLASS_MAGE':           ['ITEM_ANIMA_FIRE', 'ITEM_VULNERARY'],
    'CLASS_PRIEST':         ['ITEM_STAFF_HEAL', 'ITEM_VULNERARY'],
    'CLASS_CLERIC':         ['ITEM_STAFF_HEAL', 'ITEM_VULNERARY'],  # Basil: same kit as the
                                                                    # other healer; the classes
                                                                    # differ by promotion tree
                                                                    # and bases, not by weapon
                                                                    # (both are STAFF-only at D)
    'CLASS_ARMOR_KNIGHT':   ['ITEM_LANCE_IRON', 'ITEM_VULNERARY'],
    'CLASS_PEGASUS_KNIGHT': ['ITEM_LANCE_SLIM', 'ITEM_LANCE_JAVELIN', 'ITEM_VULNERARY'],
    'CLASS_THIEF':          ['ITEM_SWORD_IRON', 'ITEM_DOORKEY', 'ITEM_CHESTKEY',
                             'ITEM_VULNERARY'],  # Trex: the utility kit for the look-test
    'CLASS_CAVALIER':       ['ITEM_SWORD_IRON', 'ITEM_LANCE_IRON', 'ITEM_VULNERARY'],  # Baxby (mount)
    # Sahnar: sword-locked, and the Killing Edge is the point of her -- the crit threat is the
    # identity, so the look-test bench has to be able to show a crit (FE8 calls it SWORD_KILLER).
    'CLASS_MYRMIDON':       ['ITEM_SWORD_IRON', 'ITEM_SWORD_KILLER', 'ITEM_VULNERARY'],
}
# Centered, spread-out formation on the Ch1 map (a 4x2 grid, 2-tile gaps), clear of the
# houses (13,6)/(10,4) and seize (2,2). Pulled in from the old bottom-right cluster so the
# cast reads spaced out toward the middle for the look-test. Roster fills in order.
TEST_SPAWN_POSITIONS = [(5, 4), (7, 4), (9, 4), (11, 4),
                        (5, 6), (7, 6), (9, 6), (11, 6),
                        (13, 5), (13, 7), (13, 3),   # 9th-11th: recruits Trex + Baxby + Lupin
                        (3, 5), (3, 7)]              # 12th-13th: ch05's Basil + Sahnar. Left-hand
                        # column mirroring the (13,*) one, and clear of the seize tile at (2,2).

# The TESTCH sandbox doubles as the SINGLE battle-anim test bench: it deploys one hostile of
# every enemy_class_reskins slot as a foe (a row south of the cast), so `recordenemy` can bait
# any reskinned class into a counter and capture its anim -- the enemy analogue of `recordanim`
# for the PC cast (no chapter-specific setup, all animations tested from one New Game). Iron
# loadout by the reskin's BASE weapon type so the foe can actually attack/counter (anims are
# weapon-keyed); a ranged option too, to exercise the thrown/ranged modes.
CLASS_RESKIN_FOE_WEAPON = {
    'CLASS_BRIGAND':   ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE'],
    'CLASS_FIGHTER':   ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE'],
    'CLASS_MERCENARY': ['ITEM_SWORD_IRON'],
    'CLASS_SOLDIER':   ['ITEM_LANCE_IRON', 'ITEM_LANCE_JAVELIN'],
}
SANDBOX_FOE_POSITIONS = [(4, 9), (6, 9), (8, 9), (10, 9), (12, 9), (14, 9), (16, 9)]


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


def inject_opening_montage(campaign, verbose=True):
    """#43 lore crawl: re-render vanilla's seven opening-monologue slides from the
    campaign's locked card text and retime the display LUT to our word counts.
    The proc machinery (opsubtitle.c transitions, flare on slide 2, START-to-skip)
    is reused untouched -- the crawl was budgeted to seven cards for exactly that.
    Slide PNGs are decomp build inputs (make re-converts them via FETSATOOL + lz);
    stale intermediates are removed like the chap_title ones in inject_prologue."""
    montage_yaml = os.path.join(REPO, 'campaigns', campaign, 'events',
                                'opening-montage.yaml')
    cards = gen_subtitle_cards.crawl_cards(montage_yaml)
    with open(OPSUBTITLE_C, encoding='utf-8') as f:
        src = f.read()
    for i, text in enumerate(cards):
        png = os.path.join(OP_SUBTITLE_GFX_DIR, 'OpSubtitle_%02d.png' % i)
        gen_subtitle_cards.compose_card(text).save(png)
        for stale in ('.feimg2.bin', '.feimg2.bin.lz',
                      '.fetsa2.bin', '.fetsa2.bin.lz'):
            if os.path.exists(png[:-4] + stale):
                os.remove(png[:-4] + stale)
        src, n = re.subn(
            r'(gTsa_OpSubtitle_%02d,\n)(\s*)\d+(,)' % i,
            r'\g<1>\g<2>%d\g<3>' % gen_subtitle_cards.card_timer(text),
            src, count=1)
        if n == 0:
            sys.exit('ERROR: gOpSubtitleGfxLut timer for slide %d not found in %s'
                     % (i, OPSUBTITLE_C))
    # Backdrop mural: vanilla composites the slides over Img_CommGameBgScreen (the
    # brown rune wall) -- a SHARED asset (shops, chapter intro fx, ending details,
    # mural_background all decompress it), so never overwrite it. Instead point
    # opsubtitle.c's three uses at montage-local symbols and incbin our aurora-
    # township mural (book ch1 opener art, campaigns/.../events/opening-mural.png)
    # behind them. Same shape as vanilla: 640 sequential 4bpp tiles + 16-color pal.
    mural_src = os.path.join(REPO, 'campaigns', campaign, 'events',
                             'opening-mural.png')
    mural = gen_subtitle_cards.compose_mural(mural_src)
    mural_png = os.path.join(OP_SUBTITLE_GFX_DIR, 'MontageMural.png')
    mural.save(mural_png)
    with open(os.path.join(OP_SUBTITLE_GFX_DIR, 'MontageMural.gbapal'), 'wb') as f:
        f.write(gen_subtitle_cards.mural_gbapal(mural))
    for stale in ('.4bpp', '.4bpp.lz'):
        if os.path.exists(mural_png[:-4] + stale):
            os.remove(mural_png[:-4] + stale)
    src, n_img = re.subn(r'\bImg_CommGameBgScreen\b', 'Img_MontageMural', src)
    src, n_pal = re.subn(r'\bPal_08B1756C\b', 'Pal_MontageMural', src)
    if n_img != 1 or n_pal != 2:
        sys.exit('ERROR: mural symbol sites moved in %s (img %d != 1, pal %d != 2)'
                 % (OPSUBTITLE_C, n_img, n_pal))
    src = src.replace(
        '#include "constants/songs.h"',
        '#include "constants/songs.h"\n\n'
        '/* manchego #43: montage-local backdrop (vanilla rune wall is shared) */\n'
        'extern u8 CONST_DATA Img_MontageMural[];\n'
        'extern u16 CONST_DATA Pal_MontageMural[];', 1)
    with open(OPSUBTITLE_C, 'w', encoding='utf-8') as f:
        f.write(src)
    with open(DATA_OPSUBTITLE_S, encoding='utf-8') as f:
        dat = f.read()
    dat += ('\n\t.global Img_MontageMural\n'
            'Img_MontageMural:\n'
            '\t.incbin "graphics/op_subtitle/MontageMural.4bpp.lz"\n\n'
            '\t.global Pal_MontageMural\n'
            'Pal_MontageMural:\n'
            '\t.incbin "graphics/op_subtitle/MontageMural.gbapal"\n')
    with open(DATA_OPSUBTITLE_S, 'w', encoding='utf-8') as f:
        f.write(dat)
    if verbose:
        print('  lore crawl: %d slides re-rendered from %s; LUT retimed; '
              'aurora mural wired' % (len(cards), os.path.relpath(montage_yaml, REPO)))


def _tour_message_body(cards):
    """Render the town_tour cards as the WM narration message (vanilla 0x8DB
    shape): pages of up to two ~42-char lines ([LF] within a page, [A][LF]
    between pages), cards separated by [BreakTalk] -- each one is a TEXTCONT
    boundary in the event script -- and [X] terminated."""
    segs = []
    for card in cards:
        lines = _wrap_fe_lines(_fe_dialogue_text(card), width=42)
        pages = ['[LF]\n'.join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        segs.append('[A][LF]\n'.join(pages) + '[A][CR][LF]')
    return ''.join(s + '\n[BreakTalk]\n' for s in segs) + '[X]'


def _tour_event_script(card_count):
    """The prologue WM event: vanilla's opening rhythm (spawn lord, silent ->
    THE BEGINNING, drawn map revealed by WM_FADEOUT) with our two backdrops.
    Card 1 plays over map A; the swap to map B hides under a FADI/FADU pair
    (both masks leave GMAPRM_FLAG_0/1 clear = no GmapRm blends, vanilla's own
    prologue shape); 0x10 = GMAPRM_FLAG_4 selects map B in the patched
    consumer.

    The WM text window covers the bottom ~50 rows, so map B rides vanilla's
    pan trick (WM_MOVECAM2 scrolls BG1 during the drawn-map display): shown
    at y=24 for the upper-lakes cards, panned to y=48 for the Redwaters card
    (bringing Good Mead / Dougan's Hole / Easthaven above the window) and
    back for the closer. gen_drawnmap letters both maps for these scrolls.
    Ends with vanilla's FADI + SKIPWN handoff into the chapter."""
    if card_count != 6:
        sys.exit('ERROR: tour script choreography expects 6 cards, got %d'
                 % card_count)
    lines = [
        'EVBIT_MODIFY(0x1)',
        'WmEvtNoFade',
        'WM_SPAWNLORD(WM_MU_0, CHARACTER_EIRIKA, WM_NODE_BorderMulan)',
        'WM_CENTERCAMONLORD(WM_MU_0)',
        'MUSCFAST(SONG_SILENT)',
        'STAL(32)',
        'MUSC(SONG_THE_BEGINNING)',
        'WM_SHOWDRAWNMAP(0, 0, 0x0)',
        'STAL(2)',
        'WM_FADEOUT(0)',
        'WM_TEXTDECORATE',
        'EVBIT_MODIFY(0x0)',
        'STAL(40)',
        'WM_SHOWTEXTWINDOW(40, 0x0001)',
        'WM_WAITFORTEXT',
        'WM_TEXTSTART',
        'WM_TEXT(0x%04X, 0)' % TOUR_TEXT_ID,   # card 1: the dale (map A)
        'TEXTEND',
        'STAL(20)',
        'FADI(16)',
        'WM_WAITFORFXCLEAR1',   # hide the drawn map (EventB5_WmHideBigMap)
        'WM_WAITFORFXCLEAR2',   # wait for its proc to end (EventB7_WmBigMapWait)
        'WM_SHOWDRAWNMAP(0, 24, 0x10)',
        'STAL(2)',
        'FADU(16)',
        'TEXTCONT',             # card 2: Bryn Shander
        'TEXTEND',
        'STAL(20)',
        'TEXTCONT',             # card 3: Maer Dualdon towns
        'TEXTEND',
        'STAL(20)',
        'TEXTCONT',             # card 4: Lac Dinneshere towns
        'TEXTEND',
        'STAL(10)',
        'WM_MOVECAM2(0, 24, 0, 48, 50, 0)',   # pan down to the Redwaters
        'STAL(55)',
        'TEXTCONT',             # card 5: Redwaters towns
        'TEXTEND',
        'STAL(10)',
        'WM_MOVECAM2(0, 48, 0, 24, 50, 0)',   # pan back for the closer
        'STAL(55)',
        'TEXTCONT',             # card 6: closer
        'TEXTEND',
        'WM_REMOVETEXT',
        'STAL(2)',
        'FADI(16)',
        'SKIPWN',
        'ENDA',
    ]
    return '{\n' + ''.join('    %s\n' % line for line in lines) + '}'


def inject_world_tour(campaign, verbose=True):
    """#43 world-map tour: the Icewind Dale drawn maps + the prologue WM event.

    Backdrops: the two gen_drawnmap --emit assets (a-dale = whole-dale
    establishing shot, b-towns = ten-towns close-up; GIF-review pair locked
    2026-06-10) ride the WM_SHOWDRAWNMAP slot. The vanilla assets
    (Img/Pal/Tsa_EventGmap) are SHARED with vanilla ch2/ch5 WM events, so the
    consumer (GmapRm_StartUpdateDirect) is patched to montage-local symbols
    instead of overwriting them (decisions.md mural rule); the never-read
    GMAPRM_FLAG_4 mask bit selects map B (proc->flag = mask minus UNBLOCK).

    Text: the 6 locked town_tour cards become msg 0x8DB -- vanilla's WM
    narration message, referenced only by this event."""
    montage_yaml = os.path.join(REPO, 'campaigns', campaign, 'events',
                                'opening-montage.yaml')
    with open(montage_yaml, encoding='utf-8') as f:
        cards = yaml.safe_load(f)['town_tour']['cards']

    # 1. Backdrop binaries -> decomp graphics (make LZ-compresses 4bpp + tsa).
    os.makedirs(WORLD_MAP_GFX_DIR, exist_ok=True)
    for src_base, sym in (('tour-map-a-dale', 'MontageDrawnMapA'),
                          ('tour-map-b-towns', 'MontageDrawnMapB')):
        for ext in ('.4bpp', '.tsa', '.gbapal'):
            src = os.path.join(REPO, 'campaigns', campaign, 'events',
                               src_base + ext)
            if not os.path.exists(src):
                sys.exit('ERROR: %s missing -- run tools/gen_drawnmap.py --emit'
                         % src)
            dst = os.path.join(WORLD_MAP_GFX_DIR, sym + ext)
            shutil.copyfile(src, dst)
            if os.path.exists(dst + '.lz'):
                os.remove(dst + '.lz')

    with open(DATA_OPSUBTITLE_S, encoding='utf-8') as f:
        dat = f.read()
    for sym in ('MontageDrawnMapA', 'MontageDrawnMapB'):
        dat += ('\n\t.align 2, 0\n'
                '\t.global Img_%(s)s\nImg_%(s)s:\n'
                '\t.incbin "graphics/world_map/%(s)s.4bpp.lz"\n'
                '\t.align 2, 0\n'
                '\t.global Tsa_%(s)s\nTsa_%(s)s:\n'
                '\t.incbin "graphics/world_map/%(s)s.tsa.lz"\n'
                '\t.align 2, 0\n'
                '\t.global Pal_%(s)s\nPal_%(s)s:\n'
                '\t.incbin "graphics/world_map/%(s)s.gbapal"\n' % {'s': sym})
    with open(DATA_OPSUBTITLE_S, 'w', encoding='utf-8') as f:
        f.write(dat)

    # 2. Patch the consumer to the montage-local pair, selected by the mask.
    with open(WORLDMAP_RM_C, encoding='utf-8') as f:
        rm = f.read()
    rm = rm.replace(
        '#include "constants/worldmap.h"',
        '#include "constants/worldmap.h"\n\n'
        '/* manchego #43: montage-local drawn maps (vanilla EventGmap trio is\n'
        '   shared with ch2/ch5 WM events -- patch the consumer, not the data) */\n'
        'extern u8 CONST_DATA Img_MontageDrawnMapA[];\n'
        'extern u8 CONST_DATA Tsa_MontageDrawnMapA[];\n'
        'extern u16 CONST_DATA Pal_MontageDrawnMapA[];\n'
        'extern u8 CONST_DATA Img_MontageDrawnMapB[];\n'
        'extern u8 CONST_DATA Tsa_MontageDrawnMapB[];\n'
        'extern u16 CONST_DATA Pal_MontageDrawnMapB[];', 1)
    old = ('    Decompress(Img_EventGmap, (void *)BG_VRAM);\n'
           '    ApplyPalettes(Pal_EventGmap, 5, 4);\n'
           '    Decompress(Tsa_EventGmap, gGenericBuffer);\n')
    new = ('    if (proc->flag & GMAPRM_FLAG_4)\n'
           '    {\n'
           '        Decompress(Img_MontageDrawnMapB, (void *)BG_VRAM);\n'
           '        ApplyPalettes(Pal_MontageDrawnMapB, 5, 4);\n'
           '        Decompress(Tsa_MontageDrawnMapB, gGenericBuffer);\n'
           '    }\n'
           '    else\n'
           '    {\n'
           '        Decompress(Img_MontageDrawnMapA, (void *)BG_VRAM);\n'
           '        ApplyPalettes(Pal_MontageDrawnMapA, 5, 4);\n'
           '        Decompress(Tsa_MontageDrawnMapA, gGenericBuffer);\n'
           '    }\n')
    if rm.count(old) != 1:
        sys.exit('ERROR: GmapRm_StartUpdateDirect asset lines not in expected '
                 'vanilla form in %s' % WORLDMAP_RM_C)
    rm = rm.replace(old, new, 1)
    with open(WORLDMAP_RM_C, 'w', encoding='utf-8') as f:
        f.write(rm)

    # 3. The tour event + its message body.
    with open(PROLOGUE_WM_H, encoding='utf-8') as f:
        wm = f.read()
    wm = _replace_brace_block(wm, 'EventScrWM_Prologue_Beginning[] =',
                              _tour_event_script(len(cards)), PROLOGUE_WM_H)
    with open(PROLOGUE_WM_H, 'w', encoding='utf-8') as f:
        f.write(wm)

    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, TOUR_TEXT_ID, _tour_message_body(cards))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    if verbose:
        print('  world tour: %d cards -> MSG_%03X; drawn maps A (dale) + B '
              '(ten-towns) wired via GMAPRM_FLAG_4' % (len(cards), TOUR_TEXT_ID))


def _lord_select_event_seq(bg_const, explainer_msg):
    """The #46 lord-select interaction as an event-script fragment: open the scenic BG,
    show the one-time explainer ONCE, then the LABEL(0) re-pick loop (menu -> "Will N
    lead?" confirm in EVT_SLOT_C -> BNE back to the menu on "No"). Returns the fragment
    up to and INCLUDING the BNE; callers append their own tail after it -- the real ch1
    BeginningScene does EVBIT_MODIFY(0x0)+FADI+map build, the lord-fast debug boot just
    FADI+ENDA. Single home so the debug boot can't drift from the flow it claims to verify
    (CLAUDE.md design-placement rule -- one decision, one desk)."""
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


def _sandbox_foe_roster(campaign):
    """A UnitDefinition[] body deploying one hostile of each enemy_class_reskins slot, so the
    TESTCH sandbox is the single battle-anim bench (`recordenemy` baits any of them). Generic
    autolevel monsters (charIndex 0x80), FACTION_ID_RED, HOLD ai so they stay put to be baited,
    iron loadout by the reskin's BASE weapon type. A reskin whose base has no mapped weapon is
    skipped (never a foe)."""
    entries = []
    for rk, (x, y) in zip(enemy_class_reskins(campaign), SANDBOX_FOE_POSITIONS):
        weapon = CLASS_RESKIN_FOE_WEAPON.get(rk['base'])
        if not weapon:
            continue
        entries.append(
            '    {\n'
            '        .charIndex = 0x80,\n'                 # generic autolevel monster slot
            '        .classIndex = %s,\n'                  # the reskin's clone class (its sprite+anim)
            '        .leaderCharIndex = 0x80,\n'
            '        .autolevel = 1,\n'
            '        .allegiance = FACTION_ID_RED,\n'
            '        .level = 3,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '        .items = { %s },\n'
            '        .ai = {0x3, 0x3, 0x9, 0x20},\n'       # attack in place, never move -> baitable
            '    },' % (rk['slot'], x, y, ', '.join(weapon)))
    return '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'


def inject_test_chapter(campaign, verbose=True, lord_boot=False):
    """Rewrite Ch1's ally roster to our classed cast and disable Ch1 tutorials."""
    # Build the cast roster in PORTRAIT_MAP order, skipping name-only units (no class).
    units = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if class_enum not in CLASS_LOADOUT:
            sys.exit('ERROR: no test loadout for %s (unit %s)' % (class_enum, unit_id))
        units.append((unit_id, slot, class_enum, unit))
    if len(units) > len(TEST_SPAWN_POSITIONS):
        sys.exit('ERROR: %d classed cast > %d test spawn positions'
                 % (len(units), len(TEST_SPAWN_POSITIONS)))

    leader = 'CHARACTER_%s' % units[0][1].upper()  # the lord slot anchors the roster
    entries = []
    for (unit_id, slot, class_enum, unit), (x, y) in zip(units, TEST_SPAWN_POSITIONS):
        items = ', '.join(CLASS_LOADOUT[class_enum])
        entries.append(
            '    {\n'
            '        .charIndex = CHARACTER_%s,\n'
            '        .classIndex = %s,\n'
            '        .leaderCharIndex = %s,\n'
            '        .allegiance = FACTION_ID_BLUE,\n'
            '        .level = %d,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '        .items = { %s },\n'
            '    },' % (slot.upper(), deploy_class_for(unit), leader,
                        int(unit.get('fe_stats', {}).get('level', 1)),
                        x, y, items))
    roster = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'

    with open(CH1_UDEFS_H, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(
        udefs, 'UnitDef_Event_Ch1Ally[] =', roster, CH1_UDEFS_H)
    # Make the sandbox the single battle-anim bench: replace the Ch1 foe roster with one
    # hostile of every enemy_class_reskins slot (the begin scene already LOAD1s this symbol),
    # so `recordenemy` can capture any reskinned class's anim without a chapter-specific setup.
    foes = _sandbox_foe_roster(campaign)
    udefs = _replace_brace_block(
        udefs, 'UnitDef_Event_Ch1Enemy[] =', foes, CH1_UDEFS_H)
    with open(CH1_UDEFS_H, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # Empty every per-chapter event list so nothing references the removed cutscene
    # units or triggers a win/lose condition. Each is an EventListScr[] terminated by
    # END_MAIN; the tutorial list is a pointer array terminated by NULL.
    with open(CH1_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    for name in ('EventListScr_Ch1_Turn', 'EventListScr_Ch1_Character',
                 'EventListScr_Ch1_Location', 'EventListScr_Ch1_Misc'):
        info = _replace_brace_block(info, name + '[] =', '{\n    END_MAIN\n}',
                                    CH1_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch1_Tutorial[] =', '{\n    NULL\n}', CH1_EVENTINFO_H)
    with open(CH1_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # Minimal beginning scene: deploy the cast and hand over control. (Vanilla's scene
    # ran a scripted fight + forced moves that wiped our units.) LOAD1 deploys the
    # chapter's player UnitDefinition; ENUN waits for the placement; ENDA ends.
    with open(CH1_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    if lord_boot:
        # DEBUG fast-boot (#46): a pure off-map scene that mirrors the REAL ch1 lord-select
        # sequence (the SHARED _lord_select_event_seq -- explainer + re-pick loop) over the
        # scenic BG, minus only the post-Yes map build (no deploy: the menu reads
        # CharacterData, not loaded units). Verifies the explainer + "Will N lead?" confirm
        # in-engine, not just the menu. Compile-time-only iteration on the screen.
        minimal_begin = ('{\n'
                         + _lord_select_event_seq(CH01_LORDSEL_BG, LORDSEL_EXPLAINER_MSG)
                         + '    FADI(16)\n'
                           '    ENDA\n'
                           '}')
    else:
        minimal_begin = ('{\n'
                         '    LOAD1(1, UnitDef_Event_Ch1Enemy)\n'   # keep the vanilla foes (reskinned) so the sandbox is combat-ready
                         '    ENUN\n'
                         '    LOAD1(1, UnitDef_Event_Ch1Ally)\n'
                         '    ENUN\n'
                         '    ENDA\n'
                         '}')
    script = _replace_brace_block(
        script, 'EventScr_Ch1_BeginningScene[] =', minimal_begin, CH1_EVENTSCRIPT_H)
    with open(CH1_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # The boot cut + New-Game redirect (so a fresh boot lands on the title and New Game drops
    # straight onto this sandbox chapter) are the single owner _configure_boot()'s job, called
    # once from main() -- not re-decided here.
    if verbose:
        for unit_id, slot, class_enum, _ in units:
            print('  %-10s -> Ch1 ally (%s as %s)'
                  % (unit_id, slot, class_enum.replace('CLASS_', '')))
        foe_classes = [rk['slot'].replace('CLASS_', '') for rk in enemy_class_reskins(campaign)
                       if rk['base'] in CLASS_RESKIN_FOE_WEAPON]
        print('  sandbox foes (recordenemy bench): %s' % ', '.join(foe_classes))
        print('  Ch1 stripped to sandbox; boot attract + Magvel intro cut; '
              'New Game boots into Ch1')


# --- Map (overworld) sprites (#38) ------------------------------------------------
# FE8 draws map sprites by class (GetUnitSMSId -> pClassData->SMSId). To give each
# cast member a distinct overworld sprite without touching stock classes or vanilla
# enemies, we add a custom SMS slot per cast member (ids CUSTOM_SMS_BASE+) and a
# per-CHARACTER override in GetUnitSMSId. Colours come from the bespoke cast OBJ
# palette (map_sprites/cast_palette.png -> gCastMapPalette via _inject_cast_palette;
# the shared player blue bank stays untouched) -- a map sprite still can't carry its
# OWN palette, they all share the cast bank. Cold-open guests render through the
# vanilla unit_icon_pal_player.agbpal.


# --- SMS id allocation: reclaim dead vanilla rows before appending (#227) ---------
# Vanilla assigns map sprites per CLASS -- 107 wait rows serve 127 classes, because classes
# share (every Cavalier draws row 4). We assign per CHARACTER, so each custom cast member
# needs its own row. That is the design. What was NOT the design is that CUSTOM_SMS_BASE
# only ever APPENDED, leaving ~71 rows for classes this campaign can never field sitting
# unused below it while we ran into the engine's 127-id ceiling (#225).
#
# So: allocate into those dead rows first, append only when they run out.
#
# The trap is that "no class points at it" is NOT the same as "unreferenced".
# src/bmudisp.c RenderUnitSprites draws map OBJECTS by literal SMS id, no class involved:
#   0x5B/0x5C/0x5D -- ballista trap sprites, picked by trap->extra 0x35/0x36/0x37
#   0x66           -- trap type 0xD
# A class-only scan calls all four free, and reusing one renders a cast member on any map
# with a ballista. They are reserved, and a test re-derives this set from HEAD so a decomp
# bump cannot leave the reservation stale.
SMS_RESERVED_IDS = frozenset({0x5B, 0x5C, 0x5D, 0x66})


def _vanilla_class_table():
    """{CLASS_X: {'sms': id, 'promotion': CLASS_Y or None}} from the VANILLA class data.
    Read from HEAD: the working tree's data_classes.c carries our own injected clones."""
    out = {}
    for name, body in re.findall(r'\[(CLASS_\w+) - 1\] = \{(.*?)\n    \},',
                                 vanilla_decomp_text('src/data_classes.c'), re.S):
        sms = re.search(r'\.SMSId\s*=\s*(0x[0-9A-Fa-f]+|\d+)', body)
        if not sms:
            continue
        promo = re.search(r'\.promotion\s*=\s*(CLASS_\w+)', body)
        out[name] = {'sms': int(sms.group(1), 0),
                     'promotion': promo.group(1) if promo else None}
    return out


def sms_rows_for_classes(class_names):
    """The wait rows a set of vanilla classes draws from."""
    table = _vanilla_class_table()
    return {table[c]['sms'] for c in class_names if c in table}


def _promotion_branches():
    """{CLASS_X: [both promotion targets]} from FE8's BRANCHING promotion table,
    `gPromoJidLut[][2]` in src/classchg-data.c.

    ClassData.promotion holds only ONE target and is NOT the whole story: FE8 lets the
    player pick either branch (Myrmidon -> Assassin OR Swordmaster, Priest -> Bishop OR
    Sage, Thief -> Assassin OR Rogue). Following `.promotion` alone under-counts what a
    character can become, which would let us reuse the row of a class a PC can promote
    into -- and then that promotion renders as somebody else (Nicolas, 2026-08-05: the
    player should be able to class into any appropriate class, not only the one we
    prescribe)."""
    text = vanilla_decomp_text('src/classchg-data.c')
    text = text[text.index('gPromoJidLut'):]
    text = text[:text.index('};')]
    return {src: re.findall(r'CLASS_\w+', targets)
            for src, targets in re.findall(r'\[(CLASS_\w+)\]\s*=\s*\{([^}]*)\}', text)}


def _campaign_seed_classes(campaign):
    """Every vanilla class this campaign can put on screen, BEFORE promotions.

    Deliberately over-broad -- it scans raw `CLASS_*` tokens out of all campaign YAML and
    out of the event headers we author (which is where a world map names its units, #29) --
    because a missed class means a reused row and a unit rendering as somebody else. A
    false positive only costs us one reclaimable row."""
    seed = set()
    base = os.path.join(REPO, 'campaigns', campaign)
    sources = glob.glob(os.path.join(base, '**', '*.yaml'), recursive=True)
    sources += [os.path.join(DECOMP, p) for p in PATCHED_DECOMP_FILES
                if p.startswith('src/events/')]
    for path in sources:
        try:
            with open(path, encoding='utf-8') as f:
                seed |= set(re.findall(r'CLASS_[A-Z0-9_]+', f.read()))
        except (OSError, UnicodeDecodeError):
            continue
    for unit_id in PORTRAIT_MAP:
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        for enum in (class_enum_for(unit), deploy_class_for(unit)):
            if enum:
                seed.add(enum)
    # Art donors are named by SHEET, not by CLASS_ enum (art.map_sprite.base: 'Cyclops'),
    # so the token scan above misses them. Naming a vanilla class as a donor is a decent
    # signal we might also field it, and reserving costs one row.
    seed |= {'CLASS_' + name.upper() for name in _declared_donor_bases(campaign)}
    return seed | SMS_RESERVED_CLASSES


# Classes no PC holds yet but a future recruit plausibly could. Reserved by hand because
# nothing in the data can infer "we might write this character later" (#227):
#   BARD/DANCER  -- the cast already includes a bard in D&D terms
#   MANAKETE*    -- Rime of the Frostmaiden has a white dragon (Arveiaturace), so keep the
#                   WHOLE dragon family (the three are separate classes). CLASS_MANAKETE is
#                   also the only class pointing at the shared `Blank` fallback row, so
#                   reusing it would put a cast sprite on the fallback sprite
SMS_RESERVED_CLASSES = frozenset({
    'CLASS_BARD', 'CLASS_DANCER',
    'CLASS_MANAKETE', 'CLASS_MANAKETE_2', 'CLASS_MANAKETE_MYRRH',
})


def _declared_donor_bases(campaign):
    """Every `art.map_sprite.base` a campaign unit declares (vanilla sheet/class names)."""
    out = set()
    for path in glob.glob(os.path.join(REPO, 'campaigns', campaign, '**', '*.yaml'),
                          recursive=True):
        try:
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception:
            continue

        def walk(node):
            if isinstance(node, dict):
                ms = node.get('map_sprite')
                if isinstance(ms, dict) and isinstance(ms.get('base'), str):
                    out.add(ms['base'])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(data)
    return out


def sms_reachable_rows(campaign):
    """Wait rows this campaign must not reuse.

    CONSERVATIVE BY DECISION (Nicolas, 2026-08-05). The seed is not just the classes our
    YAML names today -- it is **every class in FE8's promotion tree**, i.e. anything a
    player unit could ever hold or become, whether or not this campaign fields it yet.

    Why not just today's roster: the roster is not final. Chapters and recruits are still
    being written, so a row that looks dead now can belong to a class a future PC holds --
    and "we have characters we haven't recruited yet, so your list is by definition
    incomplete" is not a bug that computation can fix. Reserving the whole player tree
    costs ~30 reclaimable rows and removes the dependency on the roster being finished.
    What is left over is genuinely un-playable: story-unique Magvel classes, the Demon
    King, spent-ballista variants, Phantom, and civilians.
    """
    table = _vanilla_class_table()
    branches = _promotion_branches()
    player_tree = set(branches) | {t for v in branches.values() for t in v}
    closure = {c for c in (_campaign_seed_classes(campaign) | player_tree) if c in table}
    frontier = set(closure)
    while frontier:
        nxt = set()
        for c in frontier:
            # BOTH branches of gPromoJidLut, plus ClassData.promotion as a belt-and-braces
            # fallback for anything the LUT does not list.
            nxt |= {t for t in branches.get(c, []) if t in table}
            if table[c]['promotion'] in table:
                nxt.add(table[c]['promotion'])
        nxt -= closure
        closure |= nxt
        frontier = nxt
    return {table[c]['sms'] for c in closure}


def sms_free_rows(campaign):
    """Vanilla wait rows this campaign can safely reuse: unreachable by any class it can
    field (after promotions) and not rendered by literal id. Recomputed every build -- if a
    later chapter fields a Wyvern Rider, that row stops being free here rather than silently
    rendering a PC as a wyvern."""
    vanilla_rows = len(re.findall(r'UNIT_ICON_SIZE',
                                  vanilla_decomp_text('src/unit_icon_wait_data.c')))
    return (set(range(vanilla_rows)) - sms_reachable_rows(campaign)) - set(SMS_RESERVED_IDS)


def allocate_sms_ids(campaign, count, verbose=False):
    """`count` SMS ids: reclaimed vanilla rows first (ascending), then appended ids past the
    end of the table. Appending stays subject to the engine ceiling (#225)."""
    free = sorted(sms_free_rows(campaign))[:count]
    ids = list(free)
    limit = sms_id_max()
    nxt = CUSTOM_SMS_BASE
    while len(ids) < count:
        if nxt > limit:
            sys.exit('ERROR: out of SMS ids -- %d requested, %d reclaimable vanilla rows + '
                     'ids %d..%d appended is all the engine can address (#225/#227).'
                     % (count, len(free), CUSTOM_SMS_BASE, limit))
        ids.append(nxt)
        nxt += 1
    if verbose and free:
        sheets = re.findall(r'unit_icon_wait_(\w+?)_sheet',
                            vanilla_decomp_text('src/unit_icon_wait_data.c'))
        print('  reclaiming %d dead vanilla SMS row(s): %s'
              % (len(free), ', '.join('%d (was %s)' % (i, sheets[i]) for i in free[:8])
                 + (' ...' if len(free) > 8 else '')))
    return ids


# The build's live SMS id pool. Module state because the two injectors that spend it --
# inject_map_sprites and inject_enemy_class_reskins -- are separate top-level passes called
# in sequence from main(), with no shared context object to thread it through. Reset once
# per build, before the first pass, so a re-run in the same process cannot double-spend.
_SMS_POOL = None


def sms_alloc_reset(campaign, verbose=False):
    """Open a fresh SMS id pool for one build: every reclaimable vanilla row (ascending),
    then the appended ids. Call once, before any sprite pass."""
    global _SMS_POOL
    free = sorted(sms_free_rows(campaign))
    _SMS_POOL = {'free': list(free), 'next_append': CUSTOM_SMS_BASE, 'reclaimed': []}
    if verbose:
        print('  SMS id pool: %d reclaimable vanilla row(s) + ids %d..%d'
              % (len(free), CUSTOM_SMS_BASE, sms_id_max()))


def claim_sms_id():
    """The next SMS id: a reclaimed dead vanilla row while any remain, else an appended id.
    Claimed ONLY by a pass that is about to write the matching wait row, which is what keeps
    ids and row indices in lockstep (allocating for a unit that never gets a row would shift
    every later row off the id naming it)."""
    if _SMS_POOL is None:
        sys.exit('ERROR: SMS id claimed before sms_alloc_reset() -- the pool is per-build')
    if _SMS_POOL['free']:
        sms = _SMS_POOL['free'].pop(0)
        _SMS_POOL['reclaimed'].append(sms)
        return sms
    sms = _SMS_POOL['next_append']
    if sms > sms_id_max():
        sys.exit('ERROR: out of SMS ids -- every reclaimable vanilla row is spent and the '
                 'append range %d..%d is full. FE8 masks ids with 0x%X, so there is no id '
                 '%d (#225/#227).' % (CUSTOM_SMS_BASE, sms_id_max(), sms_id_max(), sms))
    _SMS_POOL['next_append'] = sms + 1
    return sms


def sms_alloc_report():
    """What this build reclaimed and what is left, so reuse is legible in the build log
    instead of invisible -- and so running low is visible BEFORE the build that runs out."""
    if not _SMS_POOL:
        return
    got = _SMS_POOL['reclaimed']
    if got:
        sheets = re.findall(r'unit_icon_wait_(\w+?)_sheet',
                            vanilla_decomp_text('src/unit_icon_wait_data.c'))
        shown = ', '.join('%d (was %s)' % (i, sheets[i]) for i in got[:6])
        print('  reclaimed %d dead vanilla SMS row(s): %s%s'
              % (len(got), shown, ' ...' if len(got) > 6 else ''))
    left = len(_SMS_POOL['free']) + max(0, sms_id_max() + 1 - _SMS_POOL['next_append'])
    print('  SMS ids left: %d (%d reclaimable row(s) + %d appendable)%s'
          % (left, len(_SMS_POOL['free']), max(0, sms_id_max() + 1 - _SMS_POOL['next_append']),
             '  <-- NEARLY FULL' if left <= SMS_ID_LOW_WATER else ''))


def _write_wait_row(sms_id, row):
    """Put `row` at index `sms_id` of unit_icon_wait_table[].

    A reclaimed id REPLACES the vanilla row living there; an appended id extends the table
    and must land at exactly the index it names. Asserting that equality here is what makes
    an id/row desync impossible rather than merely unlikely."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    di, ci = _table_close_line(lines, 'unit_icon_wait_table[]')
    body = [i for i in range(di + 1, ci) if lines[i].lstrip().startswith('{')]
    if sms_id < len(body):
        lines[body[sms_id]] = row + '\n'
    else:
        if sms_id != len(body):
            sys.exit('ERROR: SMS row for id %d would land at index %d -- ids and wait-table '
                     'row indices have desynced (#227)' % (sms_id, len(body)))
        if sms_id > sms_id_max():
            sys.exit('ERROR: SMS id %d is past the engine ceiling of %d (#225)'
                     % (sms_id, sms_id_max()))
        if '},' not in lines[ci - 1] and '}' in lines[ci - 1]:
            lines[ci - 1] = re.sub(r'\}(\s*)(/[/*][^\n]*)?\n$', r'},\1\2\n',
                                   lines[ci - 1], count=1)
        lines[ci:ci] = [row + '\n']
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


def classed_cast(campaign):
    """Cast (PORTRAIT_MAP order) that carry an FE class; name-only units are skipped.

    The 4th tuple slot is a legacy None -- SMS ids are NOT assigned here. They used to be
    (CUSTOM_SMS_BASE + position, for every classed member whether or not its sprite was
    authored), which meant a classed member without art still burned an id while emitting
    no wait row, shifting every later row off the id naming it. Ids are now claimed by the
    pass that writes the matching row (claim_sms_id), so the two cannot drift (#227)."""
    out = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        if class_enum_for(unit) is None:
            continue
        out.append((unit_id, slot, class_enum_for(unit), None))
    return out


def _table_close_line(lines, decl):
    """(decl line index, closing `};` line index) for a C array `decl`."""
    di = next((i for i, ln in enumerate(lines) if decl in ln), None)
    if di is None:
        sys.exit('ERROR: %r not found' % decl)
    ci = next((i for i in range(di + 1, len(lines)) if lines[i].strip() == '};'), None)
    if ci is None:
        sys.exit('ERROR: close of %r not found' % decl)
    return di, ci


def _append_table_rows(path, decl, rows):
    """Append `rows` (source lines) before a C array's closing `};`, giving the
    previous last entry a separating comma if it lacks one."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    _, ci = _table_close_line(lines, decl)
    if '},' not in lines[ci - 1] and '}' in lines[ci - 1]:
        lines[ci - 1] = re.sub(r'\}(\s*)(/[/*][^\n]*)?\n$', r'},\1\2\n',
                               lines[ci - 1], count=1)
    lines[ci:ci] = [r + '\n' for r in rows]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


def _inject_sms_override_hook():
    """Patch GetUnitSMSId to consult the build-injected per-character override table
    before falling back to the unit's class map sprite."""
    with open(BMUNIT_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('int GetUnitSMSId(struct Unit* unit) {\n'
            '    if (!(unit->state & US_IN_BALLISTA))\n'
            '        return unit->pClassData->SMSId;\n')
    hooked = (
        'extern unsigned short gMapSpriteOverride[];\n'
        + PRE_RECRUIT_STRUCT
        + 'extern struct PreRecruitVariant gPreRecruitVariant[];\n\n'
        'int GetUnitSMSId(struct Unit* unit) {\n'
        '    if (!(unit->state & US_IN_BALLISTA)) {\n'
        '        /* Campaign per-character map-sprite override (build-injected; the\n'
        '         * table is empty in vanilla). Lets a cast member wear a custom\n'
        '         * overworld sprite its stock class -- and any enemy of that class\n'
        '         * -- does not. A cast member who has not JOINED yet wears his\n'
        '         * pre-recruit sheet instead (drawn for his side\'s palette). */\n'
        '        const unsigned short * mso = gMapSpriteOverride;\n'
        '        int charId = UNIT_CHAR_ID(unit);\n'
        + _pre_recruit_lookup('unit', '        ')
        + '        if (prv != 0)\n'
        '            return prv->smsId;\n'
        '        while (*mso != 0xFFFF) {\n'
        '            if (mso[0] == charId)\n'
        '                return mso[1];\n'
        '            mso += 2;\n'
        '        }\n'
        '        return unit->pClassData->SMSId;\n'
        '    }\n')
    if orig not in text:
        sys.exit('ERROR: GetUnitSMSId not in expected vanilla form in %s' % BMUNIT_C)
    with open(BMUNIT_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))


def lord_floor_rows(campaign, uids, ch='ch01', target=3.5):
    """Per-lord survivability-floor deltas (#45 3b): one (uid, hp, def, res) tuple per uid,
    in input order, = difficulty.lord_floor_delta vs chapter `ch`'s enemies @`target` bulk-
    durability. The engine adds the CHOSEN lord's row to its stats ONCE at chapter start
    (#45 3c), so it must stay parallel to the gLordSelectCandidates[] it is indexed against.

    Local-imports difficulty: difficulty imports this module, so a top-level import would
    cycle (HANDOFF gotcha)."""
    import difficulty
    _, _, line, bosses, _, _ = difficulty.load_field(campaign, ch)
    threat = line + bosses
    rows = []
    for uid in uids:
        f = difficulty.lord_floor_delta(
            difficulty.player_combatant(campaign, uid), threat, target=target)
        rows.append((uid, f.hp, f.df, f.res))
    return rows


def lord_select_pitches(campaign, uids):
    """Per-candidate lord-select blurbs (#46): one (uid, pitch) tuple per uid, in input
    order, read off each cast member's hand-authored `lord_pitch:` YAML. The build emits
    these as sLordSelectPitchMsg[] (eventscript TU), PARALLEL to gLordSelectCandidates[] --
    LordSelect_DrawCard draws candidate i's pitch as the cursor lands on it. Hard-fails if any candidate lacks
    a pitch: a blank card would ship silently (the "no silent gaps" lock, Nicolas
    2026-06-20)."""
    rows = []
    for uid in uids:
        pitch = load_unit(campaign, uid).get('lord_pitch')
        if not pitch:
            sys.exit('ERROR: lord-select candidate %r has no lord_pitch (#46): every '
                     'candidate needs a qualitative blurb -- no silent gaps.' % uid)
        rows.append((uid, pitch))
    return rows


def _inject_mu_override_hook():
    """Patch GetMuImg to return a per-character custom MU (hover/walk) sheet before
    the class default, reusing the class motion script (only the graphics change)."""
    with open(MU_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('const void * GetMuImg(struct MuProc * proc)\n'
            '{\n'
            '    return gMuInfoTable[proc->jid - 1].img;\n'
            '}\n')
    hooked = (
        'struct CharMuImg { unsigned short charId; const void * img; };\n'
        'extern struct CharMuImg gMuImgOverride[];\n'
        + PRE_RECRUIT_STRUCT
        + 'extern struct PreRecruitVariant gPreRecruitVariant[];\n\n'
        'const void * GetMuImg(struct MuProc * proc)\n'
        '{\n'
        '    /* Campaign per-character MU (hover/walk) sprite override (build-injected;\n'
        '     * empty in vanilla). Reuses the class motion script -- graphics only. The\n'
        '     * pre-recruit walk takes precedence while the unit has not joined you, so\n'
        '     * moving does not flip him back to his recruited colours. */\n'
        '    if (proc->unit) {\n'
        '        struct CharMuImg * it = gMuImgOverride;\n'
        '        int charId = UNIT_CHAR_ID(proc->unit);\n'
        + _pre_recruit_lookup('proc->unit', '        ')
        + '        if (prv != 0)\n'
        '            return prv->muImg;\n'
        '        while (it->charId != 0) {\n'
        '            if (it->charId == charId)\n'
        '                return it->img;\n'
        '            it++;\n'
        '        }\n'
        '    }\n'
        '    return gMuInfoTable[proc->jid - 1].img;\n'
        '}\n')
    if orig not in text:
        sys.exit('ERROR: GetMuImg not in expected vanilla form in %s' % MU_C)
    text = text.replace(orig, hooked, 1)

    # StartMu decompresses the MU graphics inside StartMuInternal -- BEFORE it sets
    # proc->unit. So the GetMuImg override (which keys on proc->unit) sees no unit on
    # that first load and falls back to the class sheet. Reload the graphics once
    # proc->unit is set so the per-character override actually applies.
    su_orig = ('    proc->unit = unit;\n'
               '    proc->cam_b = true;\n'
               '    return proc;\n')
    su_hooked = ('    proc->unit = unit;\n'
                 '    proc->cam_b = true;\n'
                 '    /* reload graphics now that proc->unit is set, so a per-character\n'
                 '     * MU override (GetMuImg) replaces the class sheet loaded above. */\n'
                 '    Decompress(GetMuImg(proc), GetMuImgBufById(proc->config->slot));\n'
                 '    return proc;\n')
    # Both StartMu and StartMuExt share this exact tail (StartMuInternal then set
    # proc->unit); patch both so any MU spawn honours the override.
    if su_orig not in text:
        sys.exit('ERROR: StartMu not in expected vanilla form in %s' % MU_C)
    text = text.replace(su_orig, su_hooked)

    with open(MU_C, 'w', encoding='utf-8') as f:
        f.write(text)


def _read_cast_palette(path):
    """Read cast_palette.png (indexed) -> 16 GBA15 u16 colours (index 0 transparent).
    Pads short palettes with black; errors if any pixel USES an index above 15 (a
    carried-but-unused longer palette, e.g. PIL's padded 256, is tolerated -- only
    the first 16 entries are read)."""
    im = Image.open(path)
    if im.mode != 'P':
        sys.exit('ERROR: %s must be indexed (mode P) so it defines the cast palette' % path)
    raw = im.getpalette() or []
    n = min(len(raw) // 3, 256)
    used = max((px for px in im.getdata()), default=0) + 1
    if used > 16:
        sys.exit('ERROR: %s uses %d palette indices; the cast bank holds 16' % (path, used))
    out = []
    for i in range(16):
        r, g, b = (raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]) if i < n else (0, 0, 0)
        out.append((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    # The engine loads this 16-colour block into the OBJ palette bank shifted one slot high:
    # empirically (rainbow test), every sprite index k displayed cast colour k-1. Pre-rotate
    # the palette up by one so each colour lands on its intended index (k -> cast[k]).
    return out[1:] + out[:1]


# Screens that load the unit-sprite palettes and then immediately ZERO the purple OBJ bank
# (0x0B). In vanilla that bank is scratch -- no vanilla unit renders from it -- but our custom
# cast map sprites do, and a zeroed 16-colour bank draws every index as colour 0, so the cast
# come out as correctly shaped BLACK SILHOUETTES (#218). Every entry is (file, exact vanilla
# text, replacement); the fill is DELETED, never re-spelled, because ApplyUnitSpritePalettes
# has already left the correct cast palette in the bank.
#
# This is a LIST and not a grep because the same idiom is spelled differently per screen --
# `PAL_OBJ(0x0B)` in prep_unitselect, the raw `gPaletteBuffer + 0x1B0` (0x100 + 0x0B*0x10) in
# unitlistscreen. Missing the second spelling is exactly how the Pick Units fix failed to
# generalise to the Character screen. A new roster screen goes here, not in a new hook.
PURPLE_BANK_BLANKERS = (
    (PREP_UNITSELECT_C,                                  # PrepUnit_InitSMS -- Pick Units
     '    ApplyUnitSpritePalettes();\n'
     '    CpuFastFill(0, PAL_OBJ(0x0B), 0x20);\n',
     '    ApplyUnitSpritePalettes();\n'
     '    /* Manchego Stars: vanilla zeros the purple OBJ bank (0x0B) here -- unused in\n'
     '     * vanilla prep -- but our custom cast map sprites render from it, so keep the\n'
     '     * cast palette ApplyUnitSpritePalettes just loaded instead of blanking it\n'
     '     * (else the roster goes black). */\n'),
    (UNITLISTSCREEN_C,                                   # UnitList_Init -- the Character list
     '    ApplyUnitSpritePalettes();\n'
     '\n'
     '    CpuFastFill(0, gPaletteBuffer + 0x1B0, PLTT_SIZE_4BPP);\n',
     '    ApplyUnitSpritePalettes();\n'
     '\n'
     '    /* Manchego Stars (#218): same blanking as PrepUnit_InitSMS, spelled as a raw\n'
     '     * gPaletteBuffer offset -- 0x1B0 == 0x100 + 0x0B*0x10 == OBJ bank 0x0B. The\n'
     '     * unit list draws each row with PutUnitSprite, so zeroing the cast bank here\n'
     '     * turned the whole roster into black silhouettes. */\n'),
)


def _drop_purple_bank_fills():
    """Delete every vanilla "zero the purple OBJ bank" fill listed in PURPLE_BANK_BLANKERS.

    Fails the build loudly if a site no longer matches verbatim: a decomp bump that reworks
    one of these screens must not silently leave that screen's roster black."""
    for path, orig, hooked in PURPLE_BANK_BLANKERS:
        with open(path, encoding='utf-8') as f:
            text = f.read()
        if orig not in text:
            sys.exit('ERROR: purple-bank (0x0B) fill not in expected form in %s -- the cast '
                     'map-sprite palette would be blanked on that screen (#218)' % path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text.replace(orig, hooked, 1))


def _inject_palette_bank_hook():
    """Patch bmudisp.c so the custom cast share a bespoke palette in the campaign-unused
    purple OBJ bank (0xB / OBJPAL_UNITSPRITE_PURPLE), leaving the shared player palette
    (blue bank) untouched -- so the not-yet-custom cast still render correctly:
      * GetUnitSpritePalette -- per-character override returning the purple bank before
        the faction switch. StartMu uses this too, so it covers idle + hover/walk; the
        grey "acted" tint is handled upstream in GetUnitDisplayedSpritePalette.
      * ApplyUnitSpritePalettes -- load gCastMapPalette into the purple bank (replacing
        the single-player Light-Rune load; Light Rune is an unused DUMMY item).

    Loading the bank is only half the job: several screens blank it again right after.
    _drop_purple_bank_fills (PURPLE_BANK_BLANKERS) is what keeps it loaded."""
    with open(BMUDISP_C, encoding='utf-8') as f:
        text = f.read()

    gsp_orig = ('int GetUnitSpritePalette(const struct Unit * unit)\n'
                '{\n'
                '    switch (UNIT_FACTION(unit)) {\n')
    gsp_hooked = (
        'extern unsigned short gMapPaletteOverride[];\n'
        + PRE_RECRUIT_STRUCT
        + 'extern struct PreRecruitVariant gPreRecruitVariant[];\n\n'
        'int GetUnitSpritePalette(const struct Unit * unit)\n'
        '{\n'
        '    /* Campaign per-character map-palette override (build-injected; empty in\n'
        '     * vanilla). Custom cast wear a bespoke palette in the purple bank so the\n'
        '     * shared player (blue) palette stays untouched -- but a cast member who\n'
        '     * has not JOINED yet must read as his SIDE (FE colours an enemy red), so\n'
        '     * he skips the override and falls through to the faction switch, wearing\n'
        '     * the pre-recruit sheet drawn for those standard palettes. */\n'
        '    const unsigned short * mp = gMapPaletteOverride;\n'
        '    int charId = UNIT_CHAR_ID(unit);\n'
        + _pre_recruit_lookup('unit')
        + '    if (prv == 0) {\n'
        '        while (*mp != 0xFFFF) {\n'
        '            if (*mp == charId)\n'
        '                return OBJPAL_UNITSPRITE_PURPLE;\n'
        '            mp++;\n'
        '        }\n'
        '    }\n'
        '    switch (UNIT_FACTION(unit)) {\n')
    if gsp_orig not in text:
        sys.exit('ERROR: GetUnitSpritePalette not in expected vanilla form in %s' % BMUDISP_C)
    text = text.replace(gsp_orig, gsp_hooked, 1)

    au_sig_orig = 'void ApplyUnitSpritePalettes(void)\n{\n'
    au_sig_hooked = ('extern unsigned short gCastMapPalette[];\n\n'
                     'void ApplyUnitSpritePalettes(void)\n{\n')
    if au_sig_orig not in text:
        sys.exit('ERROR: ApplyUnitSpritePalettes not in expected vanilla form in %s' % BMUDISP_C)
    text = text.replace(au_sig_orig, au_sig_hooked, 1)

    au_orig = ('    else\n'
               '        ApplyPalette(gPal_LightRune, 0x10 + OBJPAL_UNITSPRITE_PURPLE);\n')
    au_hooked = ('    else\n'
                 '        /* Manchego Stars: custom cast share a bespoke 16-colour palette\n'
                 '         * in the (campaign-unused) purple bank; vanilla loads the unused\n'
                 '         * Light Rune palette here. */\n'
                 '        ApplyPalette(gCastMapPalette, 0x10 + OBJPAL_UNITSPRITE_PURPLE);\n')
    if au_orig not in text:
        sys.exit('ERROR: ApplyUnitSpritePalettes Light-Rune load not found in %s' % BMUDISP_C)
    text = text.replace(au_orig, au_hooked, 1)

    with open(BMUDISP_C, 'w', encoding='utf-8') as f:
        f.write(text)

    _drop_purple_bank_fills()


def _inject_cast_palette(palette_u16, char_slots, extra_char_ids=()):
    """Emit gCastMapPalette (the bespoke 16-colour bank) + gMapPaletteOverride (the
    charIds that wear it, 0xFFFF-terminated) into the kept .data file, then patch the
    bmudisp palette hooks. char_slots = portrait-slot names (-> CHARACTER_<SLOT>);
    extra_char_ids = RAW charId literals for units with no portrait slot (scripted
    neutrals, which wear this palette precisely because they never change faction)."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        wait_c = f.read()
    if 'constants/characters.h' not in wait_c:
        wait_c = wait_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    pal = ', '.join('0x%04X' % c for c in palette_u16)
    ov = '\n'.join(['\tCHARACTER_%s,' % s.upper() for s in char_slots]
                   + ['\t%s,' % c for c in extra_char_ids])
    wait_c += ('\n/* injected: bespoke cast map-sprite palette (loaded into the purple OBJ\n'
               ' * bank) + the charIds that wear it (0xFFFF-terminated). Non-const so they\n'
               ' * share unit_icon_wait_table\'s kept .data section. */\n'
               'unsigned short gCastMapPalette[16] = { %s };\n' % pal
               + 'unsigned short gMapPaletteOverride[] = {\n' + ov + '\n\t0xFFFF\n};\n')
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(wait_c)
    _inject_palette_bank_hook()


# Cast members rendered through the SIDE (faction) palette -- green as an NPC, then the
# standard blue PLAYER palette once recruited -- instead of the bespoke cast OBJ palette.
# Their custom SHAPE still ships (SMS + MU overrides), but the sheet is remapped onto the
# donor class's standard SMS role layout (cf. enemy reskins / the ch02 chwinga) and the
# unit is kept OUT of gMapPaletteOverride, so GetUnitSpritePalette falls through to the
# faction switch and tints it per side. Needed for a unit that CHANGES faction colour in
# play: Trex stands GREEN, then the talk-recruit CUSA flips him to the BLUE player palette
# (#23). A charId-keyed cast override is unconditional -- it would pin one colour, so a
# green Trex would wrongly render in his blue player palette (Nicolas, 2026-07-10).
FACTION_TINTED_CAST = frozenset({'trex'})


def inject_map_sprites(campaign, verbose=True):
    """Give cast members a custom overworld sprite distinct from their class.

    Two sheets per character, both optional and added one at a time (no asset -> the
    unit keeps its stock-class sprite; stock classes and vanilla enemies untouched):
      * map_sprites/<id>.png      -> IDLE (wait sheet): a custom SMS slot (id 107+)
        plus a GetUnitSMSId per-character override.
      * map_sprites/<id>_mu.png   -> HOVER/WALK (MU sheet, 32x480): a custom move sheet
        plus a GetMuImg per-character override (reuses the class motion script)."""
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    # An id is claimed only for a member that actually HAS a sheet, i.e. only where a wait
    # row is about to be written -- see claim_sms_id (#227).
    idle = [(uid, slot, cls, claim_sms_id()) for (uid, slot, cls, _) in classed_cast(campaign)
            if os.path.isfile(os.path.join(asset_dir, uid + '.png'))]

    # Cold-open guests (PROLOGUE_GUEST_SPRITES) get the same SMS/MU overrides but render
    # through FE8's standard player palette -- so they are kept out of custom_slots (no
    # cast-palette override) below.
    guest_idle, guest_bases = [], {}
    for uid, slot, cls, base in PROLOGUE_GUEST_SPRITES:
        if os.path.isfile(os.path.join(asset_dir, uid + '.png')):
            guest_idle.append((uid, slot, cls, claim_sms_id()))
            guest_bases[uid] = base

    if not idle and not guest_idle:
        if verbose:
            print('  (no map_sprites/*.png assets yet; cast keep their class sprites)')
        return

    # MU (hover/walk) sheet per idle character: a committed <id>_mu.png if hand-authored,
    # else a static "glide" sheet synthesized from the finished idle frame so a MOVING
    # unit keeps its custom sprite instead of reverting to the stock class one (idle-only
    # decision -- map_sprite_tool.synth_mu_sheet). Synthesized sheets go to a temp dir so
    # no derived asset lands in the working tree; the single source of truth is the idle.
    # Faction-tinted cast (Trex): remap the cast-palette idle + committed walk onto the
    # donor class's standard SMS role layout so the faction switch tints them (green NPC ->
    # blue player on recruit). Same remap as enemy reskins, using the donor WAIT sheet's
    # palette for BOTH sheets so idle/walk share role indices. Temp dir -> no derived asset
    # in the tree (single source of truth stays map_sprites/<id>.png).
    tinted_idle_src, tinted_mu_src, tint_tmp = {}, {}, None
    for uid, slot, cls, sms in idle:
        if uid not in FACTION_TINTED_CAST:
            continue
        if tint_tmp is None:
            tint_tmp = tempfile.mkdtemp(prefix='manchego_tint_')
        donor_png = os.path.join(WAIT_GFX_DIR,
                                 'unit_icon_wait_%s_sheet.png' % _donor_base(campaign, uid))
        r_idle = os.path.join(tint_tmp, uid + '.png')
        map_sprite_tool.remap_sms_palette(os.path.join(asset_dir, uid + '.png'), donor_png, r_idle)
        tinted_idle_src[uid] = r_idle
        committed_mu = os.path.join(asset_dir, uid + '_mu.png')
        if os.path.isfile(committed_mu):
            r_mu = os.path.join(tint_tmp, uid + '_mu.png')
            map_sprite_tool.remap_sms_palette(committed_mu, donor_png, r_mu)
            tinted_mu_src[uid] = r_mu

    mu, mu_tmp = [], None
    for uid, slot, cls, sms in idle:
        if uid in tinted_mu_src:                     # faction-tinted committed walk (remapped)
            mu.append((uid, slot, cls, tinted_mu_src[uid]))
            continue
        committed = os.path.join(asset_dir, uid + '_mu.png')
        if uid not in FACTION_TINTED_CAST and os.path.isfile(committed):
            mu.append((uid, slot, cls, committed))
            continue
        if mu_tmp is None:
            mu_tmp = tempfile.mkdtemp(prefix='manchego_mu_')
        src = os.path.join(mu_tmp, uid + '_mu.png')
        nudge = ((load_unit(campaign, uid).get('art') or {}).get('map_sprite') or {}).get(
            'glide_nudge', 0)
        # A tinted unit with no committed walk glides from its REMAPPED role idle (so the
        # glide tints too); everyone else glides from their raw cast-palette idle.
        idle_for_synth = tinted_idle_src.get(uid, os.path.join(asset_dir, uid + '.png'))
        map_sprite_tool.synth_mu_sheet(idle_for_synth,
                                       _donor_base(campaign, uid), src,
                                       y_nudge=nudge, verbose=verbose)
        mu.append((uid, slot, cls, src))

    # Guests must ship a committed hover/walk sheet (no synth path -- that machinery reads
    # the cast palette / unit YAML, neither of which a standard-palette guest carries).
    guest_mu = []
    for uid, slot, cls, sms in guest_idle:
        committed = os.path.join(asset_dir, uid + '_mu.png')
        if not os.path.isfile(committed):
            sys.exit('ERROR: guest sprite %s needs a committed map_sprites/%s_mu.png '
                     '(hover/walk sheet; guests have no synth path)' % (uid, uid))
        guest_mu.append((uid, slot, cls, committed))

    pointer_externs = []
    _inject_idle_sprites(campaign, asset_dir, idle + guest_idle, pointer_externs, guest_bases,
                         src_override=tinted_idle_src)
    _inject_mu_sprites(mu + guest_mu, pointer_externs)
    # Second look for a cast member who is on the field BEFORE he joins you (appends its
    # own wait rows, so it must follow the cast/guest rows that name their own SMS ids).
    _inject_pre_recruit_variants(campaign, idle, pointer_externs, verbose=verbose)
    # Scripted neutrals (ch04's white moose): custom art on a unit that is not cast, so
    # classed_cast never sees it. Must follow the cast/guest passes -- it appends its own
    # wait rows and reaches into the override tables those passes emit.
    neutral_ids = _inject_scripted_neutral_sprites(campaign, asset_dir, pointer_externs,
                                                   verbose=verbose)
    if pointer_externs:
        with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars custom map sprites (#38) */\n'
                    + '\n'.join(pointer_externs) + '\n')

    # Any cast with a custom sprite (idle and/or MU) wears the bespoke cast palette in
    # its own OBJ bank -- its sheet is drawn to the cast-palette indices, so it must be
    # viewed through that palette (decisions.md Art & Audio).
    # Faction-tinted cast wear the side palette, not the cast override -> excluded here.
    custom_slots = [slot for uid, slot, _, _ in idle if uid not in FACTION_TINTED_CAST]
    custom_slots += [slot for uid, slot, _, _ in mu
                     if uid not in FACTION_TINTED_CAST and slot not in custom_slots]
    if custom_slots or neutral_ids:
        pal_png = os.path.join(asset_dir, 'cast_palette.png')
        if not os.path.isfile(pal_png):
            sys.exit('ERROR: custom map sprites need campaigns/%s/map_sprites/cast_palette.png'
                     % campaign)
        # Scripted neutrals join the override by RAW charId -- they have no portrait slot.
        _inject_cast_palette(_read_cast_palette(pal_png), custom_slots,
                             extra_char_ids=[cid for _, cid, _ in neutral_ids])

    # ch02 green chwinga: reskin minor NPC slots with Sclorbo's chwinga map sprite, tinted
    # by the green faction palette (no bespoke palette -- they're green faction). Runs here
    # because inject_map_sprites owns the gMapSpriteOverride / gMuImgOverride tables.
    _inject_ch02_chwinga_sprites(campaign, verbose=verbose)

    # Everything declared + committed must have landed in one of the passes above.
    assert_declared_map_sprites_injected(campaign, {uid for uid, _, _, _ in idle + guest_idle}
                                         | {uid for uid, _, _, _ in mu + guest_mu}
                                         | {uid for uid, _, _ in neutral_ids}
                                         | {CH02_CHWINGA_SPRITE_SRC})

    if verbose:
        guest_uids = {uid for uid, _, _, _ in guest_idle}
        for uid, slot, class_enum, sms in idle + guest_idle:
            tag = ' [guest, std palette]' if uid in guest_uids else ''
            print('  %-14s -> idle SMS %d (%s)%s' % (uid, sms, slot, tag))
        for uid, slot, class_enum, src in mu + guest_mu:
            kind = 'committed' if os.path.dirname(src) == asset_dir else 'glide'
            print('  %-14s -> hover/walk MU sheet (%s, %s)' % (uid, slot, kind))
        if custom_slots:
            print('  cast palette -> purple OBJ bank for: %s' % ', '.join(custom_slots))


def _insert_table_head(path, decl, rows_text):
    """Insert `rows_text` right after a C array's `decl ... = {` opener (front of the
    table). Used to add entries to an already-emitted, terminator-closed override table
    without keying on the terminator (which several tables in the same file share)."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    m = re.search(re.escape(decl) + r'[^\n]*\{\n', text)
    if not m:
        sys.exit('ERROR: %r opener not found in %s' % (decl, path))
    text = text[:m.end()] + rows_text + text[m.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


# --- pre-recruit variant: a cast member who is on the field before he joins you ---------
# A charId-keyed cast override is UNCONDITIONAL, so a cast member placed on a hostile/NPC
# side renders in his bespoke cast palette regardless -- the Trex bug (decisions.md Art &
# Audio). FACTION_TINTED_CAST solves it by giving up the cast palette entirely, which is
# right when the joined look may be the side's standard blue. It is NOT right when the
# joined look IS the bespoke sheet (Lupin: red as the pack's leader, the finalized grey
# once recruited). So: a SECOND sheet in the standard SMS role layout, worn only while the
# unit is not on the player side, derived at build time from the cast sheet by an index
# remap (art.map_sprite.pre_recruit_roles) -- single source of truth stays the cast sheet.
# The engine picks between them in the three per-character override hooks below.
PRE_RECRUIT_STRUCT = ('struct PreRecruitVariant { unsigned short charId; '
                      'unsigned short smsId; const void * muImg; };\n')


def _pre_recruit_lookup(unit_expr, indent='    ', char_var='charId'):
    """C (agbcc/C89: declarations first) resolving `unit_expr` to its pre-recruit variant
    row, or NULL when the unit has joined / has no variant.

    `char_var` names an int the CALLER has already set to the unit's charId -- all three
    override hooks compute one for their own table scan, so the lookup reuses it rather
    than recomputing UNIT_CHAR_ID into a second local."""
    i = indent
    return (i + 'struct PreRecruitVariant * prv = 0;\n'
            + i + 'if (UNIT_FACTION(%s) != FACTION_BLUE) {\n' % unit_expr
            + i + '    struct PreRecruitVariant * prvIt = gPreRecruitVariant;\n'
            + i + '    while (prvIt->charId != 0) {\n'
            + i + '        if (prvIt->charId == %s) {\n' % char_var
            + i + '            prv = prvIt;\n'
            + i + '            break;\n'
            + i + '        }\n'
            + i + '        prvIt++;\n'
            + i + '    }\n'
            + i + '}\n')


def pre_recruit_roles(campaign, uid):
    """{cast index: standard SMS role index} for a unit that stands on a non-player side
    before it joins, or None. Declared in the unit YAML (art.map_sprite.pre_recruit_roles)."""
    ms = ((load_unit(campaign, uid).get('art') or {}).get('map_sprite') or {})
    roles = ms.get('pre_recruit_roles')
    return {int(k): int(v) for k, v in roles.items()} if roles else None


def _inject_pre_recruit_variants(campaign, idle, pointer_externs, verbose=True):
    """Emit the pre-recruit (not-yet-joined) sheets + gPreRecruitVariant for every cast
    member declaring `pre_recruit_roles`. Runs inside inject_map_sprites, which owns the
    override tables; the table is always emitted (empty == vanilla behaviour)."""
    rows = []
    for uid, slot, _cls, _sms in idle:
        roles = pre_recruit_roles(campaign, uid)
        if not roles:
            continue
        asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
        donor = _donor_base(campaign, uid)
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor)
        sym = 'unit_icon_wait_manchego_%s_pre_sheet' % uid.replace('-', '_')
        move_sym = 'unit_icon_move_manchego_%s_pre_sheet' % uid.replace('-', '_')
        wait_png = os.path.join(WAIT_GFX_DIR, sym + '.png')
        move_png = os.path.join(MOVE_GFX_DIR, move_sym + '.png')
        donor_png = os.path.join(WAIT_GFX_DIR, 'unit_icon_wait_%s_sheet.png' % donor)
        for src, dst in ((uid + '.png', wait_png), (uid + '_mu.png', move_png)):
            src = os.path.join(asset_dir, src)
            if not os.path.isfile(src):
                sys.exit('ERROR: %s declares pre_recruit_roles but has no map_sprites/%s'
                         % (uid, os.path.basename(src)))
            _remap_indices(src, roles, donor_png, dst)
        map_sprite_tool.validate_mu_sheet(move_png)
        macro, _, _, _ = map_sprite_tool.sheet_info(wait_png, (dfw, dfh))

        sms = claim_sms_id()
        _write_wait_row(sms,
            '\t{0, %s, %s}, // %d %s (pre-recruit)' % (macro, sym, sms, uid))
        with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars pre-recruit idle sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, sym, sym, sym))
        with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars pre-recruit hover/walk (MU) sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, move_sym, move_sym, move_sym))
        pointer_externs += ['extern char %s[];' % sym, 'extern char %s[];' % move_sym]
        rows.append('\t{CHARACTER_%s, %d, %s},' % (slot.upper(), sms, move_sym))
        if verbose:
            print('  %-12s -> pre-recruit sheet (SMS %d) worn until he joins you' % (uid, sms))

    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        move_c = f.read()
    move_c += ('\n/* injected: pre-recruit (not-yet-joined) map sprites -- a cast member on a\n'
               ' * hostile/NPC side wears THIS standard-palette sheet under his side\'s\n'
               ' * faction colour instead of the bespoke cast palette. charId 0 terminates;\n'
               ' * an empty table is exactly vanilla behaviour. */\n'
               + PRE_RECRUIT_STRUCT
               + 'struct PreRecruitVariant gPreRecruitVariant[] = {\n'
               + ('\n'.join(rows) + '\n' if rows else '') + '\t{0, 0, 0}\n};\n')
    with open(UNIT_ICON_MOVE_C, 'w', encoding='utf-8') as f:
        f.write(move_c)


def _remap_indices(src_path, roles, palette_png, out_path):
    """Rewrite an indexed sheet's pixel INDICES through `roles` (index -> index), saving it
    under `palette_png`'s palette. Index 0 (transparent) is fixed. Unlike
    map_sprite_tool.remap_sms_palette this is an explicit ROLE map, not nearest-RGB: the
    cast sheets are a grey ramp, and nearest-RGB against a coloured standard palette
    collapses them onto the constant/secondary entries (a grey Lupin barely changes colour
    by faction). Every non-zero index present must be declared."""
    im = Image.open(src_path)
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; expected an indexed (mode P) sheet' % (src_path, im.mode))
    missing = sorted({v for v in im.getdata() if v and v not in roles})
    if missing:
        sys.exit('ERROR: %s uses cast index/indices %s with no pre_recruit_roles entry'
                 % (os.path.basename(src_path), ', '.join(str(m) for m in missing)))
    out = Image.new('P', im.size)
    out.putpalette(map_sprite_tool.read_palette(palette_png))
    out.putdata([0 if v == 0 else roles[v] for v in im.getdata()])
    out.save(out_path)


def declared_map_sprite_units(campaign):
    """Every campaign unit that DECLARES custom map-sprite art -- cast (pcs/npcs YAML) and
    chapter-level scripted neutrals alike -- as {id: where-it-was-declared}."""
    declared = {}
    root = os.path.join(REPO, 'campaigns', campaign)
    for sub in ('pcs', 'npcs'):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith('.yaml'):
                continue
            with open(os.path.join(d, name), encoding='utf-8') as f:
                unit = yaml.safe_load(f) or {}
            ms = (unit.get('art') or {}).get('map_sprite')
            if ms and (ms or {}).get('wiring') != 'pending':
                declared[unit.get('id') or name[:-5]] = '%s/%s' % (sub, name)
    chapters = os.path.join(root, 'chapters')
    for name in sorted(os.listdir(chapters)):
        if not name.endswith('.yaml'):
            continue
        with open(os.path.join(chapters, name), encoding='utf-8') as f:
            chap = yaml.safe_load(f) or {}
        for key in ('neutral_units', 'green_units'):
            for unit in (chap.get(key) or []):
                if ((unit.get('art') or {}).get('map_sprite')) and unit.get('id'):
                    declared[unit['id']] = 'chapters/%s (%s)' % (name, key)
    return declared


def assert_declared_map_sprites_injected(campaign, wired):
    """Custom map art that is DECLARED and COMMITTED must actually get wired, or the unit
    silently wears its stock class sprite and nothing anywhere complains.

    That is precisely how ch04's white moose shipped: a full `art:` block on the chapter YAML,
    two committed Wyrdeer sheets, and an injector that only ever walked PORTRAIT_MAP -- so the
    chapter's title creature rendered as CLASS_GWYLLGI's stock hound. There was no error to
    read, because nothing tried and failed; nothing tried at all. A missing ASSET stays a
    no-op (art lands before wiring, deliberately) -- what fails here is art that exists on
    disk and is described in YAML, yet ends up in no sprite table.

    Art routinely lands one slice AHEAD of its wiring (Basil/Sahnar shipped with #179/#181;
    their wiring is #25 ch05 work). That deferral is legitimate, but it has to be WRITTEN
    DOWN or this guard cannot tell it from the moose -- so say `wiring: pending` on the unit's
    map_sprite block and name the issue there.
    """
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    missing = sorted(
        (uid, where) for uid, where in declared_map_sprite_units(campaign).items()
        if os.path.isfile(os.path.join(asset_dir, uid + '.png')) and uid not in wired)
    if missing:
        sys.exit('ERROR: these units declare art.map_sprite and ship map_sprites/<id>.png, '
                 'but no injector wired them -- they would render their stock class sprite:\n'
                 + '\n'.join('       %-16s declared in %s' % (uid, where) for uid, where in missing)
                 + '\n       Cast go in PORTRAIT_MAP; scripted neutrals in '
                   'SCRIPTED_NEUTRAL_SPRITES.')


def _inject_scripted_neutral_sprites(campaign, asset_dir, pointer_externs, verbose=True):
    """Map sprites for SCRIPTED NEUTRALS -- units that stand on a map wearing our own art but
    are NOT cast members (no PORTRAIT_MAP slot, no bust/stat/prep wiring), so `classed_cast`
    never sees them and `inject_map_sprites` used to walk straight past their assets.

    That gap is how ch04's white moose shipped: its Wyrdeer sheets and a full `art:` block
    were committed on the chapter YAML, nothing read them, and the engine fell back to
    CLASS_GWYLLGI's stock hound -- a green dog standing in for the chapter's title creature.
    Nothing failed; the art was simply never asked for. `assert_declared_map_sprites_injected`
    now closes that door.

    They wear the CAST palette, not the faction one, which is the whole reason they can't ride
    the chwinga path: a scripted neutral never changes faction, and the green NPC palette turns
    index 3 pale-green and index 11 blue -- a green-tinted animal with green blood. Keyed by a
    RAW charId (a pid the injector allocated), not a portrait-slot name.
    """
    neutral_ids = []
    for uid, char_id, donor in SCRIPTED_NEUTRAL_SPRITES:
        idle_png = os.path.join(asset_dir, uid + '.png')
        if not os.path.isfile(idle_png):
            continue
        mu_png = os.path.join(asset_dir, uid + '_mu.png')
        if not os.path.isfile(mu_png):
            sys.exit('ERROR: scripted neutral %s needs a committed map_sprites/%s_mu.png '
                     '(hover/walk sheet; neutrals have no synth path -- synth_mu_sheet reads '
                     'the unit YAML, which a chapter-level neutral has none of)' % (uid, uid))
        map_sprite_tool.validate_mu_sheet(mu_png)
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor)
        macro, _, _, _ = map_sprite_tool.sheet_info(idle_png, (dfw, dfh))
        stem = uid.replace('-', '_')
        wait_sym = 'unit_icon_wait_manchego_%s_sheet' % stem
        move_sym = 'unit_icon_move_manchego_%s_sheet' % stem
        shutil.copyfile(idle_png, os.path.join(WAIT_GFX_DIR, wait_sym + '.png'))
        shutil.copyfile(mu_png, os.path.join(MOVE_GFX_DIR, move_sym + '.png'))
        sms = claim_sms_id()
        _write_wait_row(sms,
            '\t{0, %s, %s}, // %d %s (scripted neutral)' % (macro, wait_sym, sms, uid))
        with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars scripted-neutral idle sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, wait_sym, wait_sym, wait_sym))
        with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars scripted-neutral hover/walk (MU) sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, move_sym, move_sym, move_sym))
        pointer_externs += ['extern char %s[];' % wait_sym, 'extern char %s[];' % move_sym]
        _insert_table_head(UNIT_ICON_WAIT_C, 'gMapSpriteOverride[]',
                           '\t%s, %d,\n' % (char_id, sms))
        _insert_table_head(UNIT_ICON_MOVE_C, 'gMuImgOverride[]',
                           '\t{%s, %s},\n' % (char_id, move_sym))
        neutral_ids.append((uid, char_id, sms))
        if verbose:
            print('  %-12s -> scripted-neutral idle SMS %d + MU (charId %s, cast palette)'
                  % (uid, sms, char_id))
    return neutral_ids


def _inject_ch02_chwinga_sprites(campaign, verbose=True):
    """The 3 green chwinga (CH02_CHWINGA slots) wear Sclorbo's chwinga map sprite,
    recoloured by the GREEN NPC faction palette. They are green-faction, so they are kept
    OUT of the cast palette override (gMapPaletteOverride) -- GetUnitSpritePalette falls to
    the faction switch and tints the standard role layout green automatically (cf. the
    enemy reskins, which do the same for the red faction). Sclorbo's cast-palette sheet is
    remapped onto his SMS base's standard role layout at build time, so the single source
    of truth stays sclorbo.png (no committed derived asset); one shared SMS slot + MU sheet
    serve all three identical NPC slots. Must run inside inject_map_sprites (it owns the
    gMapSpriteOverride / gMuImgOverride tables)."""
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    src_idle = os.path.join(asset_dir, CH02_CHWINGA_SPRITE_SRC + '.png')
    if not os.path.isfile(src_idle):
        if verbose:
            print('  (no %s.png yet; chwinga keep their class sprite)' % CH02_CHWINGA_SPRITE_SRC)
        return
    donor = _donor_base(campaign, CH02_CHWINGA_SPRITE_SRC)        # 'Civilian_F1'
    donor_png = os.path.join(WAIT_GFX_DIR, 'unit_icon_wait_%s_sheet.png' % donor)
    _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor)

    wait_sym = 'unit_icon_wait_manchego_chwinga_sheet'
    move_sym = 'unit_icon_move_manchego_chwinga_sheet'
    role_idle = os.path.join(WAIT_GFX_DIR, wait_sym + '.png')
    move_png = os.path.join(MOVE_GFX_DIR, move_sym + '.png')
    # Remap Sclorbo's cast-palette tiles onto the donor's standard role layout (so the
    # green faction palette tints them), then synth the idle-only glide MU sheet from it.
    map_sprite_tool.remap_sms_palette(src_idle, donor_png, role_idle)
    map_sprite_tool.synth_mu_sheet(role_idle, donor, move_png, verbose=False)
    macro, _, _, _ = map_sprite_tool.sheet_info(role_idle, (dfw, dfh))

    sms = claim_sms_id()
    _write_wait_row(sms,
        '\t{0, %s, %s}, // %d chwinga (green NPC)' % (macro, wait_sym, sms))
    with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars green chwinga idle sprite (#38) */\n'
                '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n'
                '\t.align 2, 0\n' % (wait_sym, wait_sym, wait_sym))
    with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars green chwinga hover/walk (MU) sprite (#38) */\n'
                '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n'
                '\t.align 2, 0\n' % (move_sym, move_sym, move_sym))
    with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars green chwinga map sprite (#38) */\n'
                'extern char %s[];\nextern char %s[];\n' % (wait_sym, move_sym))

    # The three NPC slots all override onto the one shared chwinga slot/sheet. Insert at
    # the front of each table (linear scan; chwinga charIds are distinct from cast slots).
    slots = [slot for _, slot in CH02_CHWINGA]
    _insert_table_head(UNIT_ICON_WAIT_C, 'gMapSpriteOverride[]',
                       ''.join('\tCHARACTER_%s, %d,\n' % (s.upper(), sms) for s in slots))
    _insert_table_head(UNIT_ICON_MOVE_C, 'gMuImgOverride[]',
                       ''.join('\t{CHARACTER_%s, %s},\n' % (s.upper(), move_sym) for s in slots))
    if verbose:
        print('  chwinga (green NPC) -> idle SMS %d + MU, slots: %s'
              % (sms, ', '.join(slots)))


def inject_ch02_chwinga_faces(campaign, verbose=True):
    """Dress the 3 green chwinga (CH02_CHWINGA) with Sclorbo's bust recoloured green + their
    fe_names. The bust is build-derived from sclorbo.png -- the blue glow ramp hue-shifted to
    spirit-green, the same swap as the map sprite -- so the single source stays Sclorbo's
    portrait (no committed derived asset). Each chwinga's vanilla portrait slot is collision-
    free; names come from the ch02 YAML (deployment.green_allies fe_name)."""
    bust_path = os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')
    if not os.path.isfile(bust_path):
        if verbose:
            print('  (no %s bust yet; chwinga keep vanilla faces/names)' % CH02_CHWINGA_SPRITE_SRC)
        return
    # 1. recolour Sclorbo's bust: blue glow ramp -> spirit-green (by source RGB).
    im = Image.open(bust_path).convert('P')
    pal = list(im.getpalette()[:48])
    for i in range(16):
        rgb = tuple(pal[i * 3:i * 3 + 3])
        if rgb in CH02_CHWINGA_GLOW_RECOLOR:
            pal[i * 3:i * 3 + 3] = list(CH02_CHWINGA_GLOW_RECOLOR[rgb])
    chwinga_bust = im.copy()
    chwinga_bust.putpalette(pal)
    tileset, mouth, chibi, pal_bytes = portrait_tool.generate(chwinga_bust, static_portrait=True)

    # 2. dress each chwinga's collision-free portrait slot with the one shared green bust.
    for vanilla in CH02_CHWINGA_PORTRAIT_SLOT.values():
        base = os.path.join(PORTRAIT_DIR, 'portrait_' + vanilla)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)

    # 3. name each chwinga slot from the ch02 YAML fe_name (Mote / Rime / Glimmer).
    chap = _load_chapter_yaml(campaign, CH02_CHAPTER_YAML)
    by_id = {g['id']: g for g in chap['deployment']['green_allies']}
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for uid, slot in CH02_CHWINGA:
        set_message_body(lines, vanilla_name_text_id(slot),
                         name_message_body(display_name(by_id[uid])))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    if verbose:
        names = ', '.join(display_name(by_id[uid]) for uid, _ in CH02_CHWINGA)
        print('  chwinga faces -> %s (shared green bust + names: %s)'
              % (', '.join(CH02_CHWINGA_PORTRAIT_SLOT.values()), names))


def _vendor_mug_to_bust(path, recolor=None):
    """A 128x112 FE-Repo mug sheet -> the 96x80 indexed bust portrait_tool.generate() wants.

    The community sheets are one main frame at top-left plus speaking/blink frames; we take the
    main frame only (our busts are static -- decisions.md, Art & Audio). The background key is
    read from the CORNER PIXEL rather than hardcoded, because it is not one colour across the
    repo: Glaceo's set keys on (123,162,115) and Eden/L95's on (160,200,152), and hardcoding
    either silently leaves a green box behind the other artist's faces.

    `recolor` maps source RGB -> replacement, applied before indexing, for pulling two mugs that
    share a body apart (see CH05_VISIT_FACES).

    FE8 portraits are 16 colours INCLUDING the transparent key, so index 0 is forced to magenta
    and the rest follow. A mug that does not fit is a hard error, not a silent quantize: dithering
    a pixel-art bust to fit would wreck the flats it is drawn in.
    """
    im = Image.open(path).convert('RGB').crop((0, 0, 96, 80))
    key = im.getpixel((0, 0))
    px = im.load()
    for y in range(80):
        for x in range(96):
            colour = px[x, y]
            if colour == key:
                px[x, y] = PORTRAIT_TRANSPARENT_RGB
            elif recolor and colour in recolor:
                px[x, y] = recolor[colour]
    colours = [c for _, c in im.getcolors(1 << 16)]
    if len(colours) > 16:
        sys.exit('ERROR: %s needs %d colours; an FE8 portrait holds 16 including the '
                 'transparent key.' % (os.path.basename(path), len(colours)))
    palette = ([PORTRAIT_TRANSPARENT_RGB]
               + [c for c in colours if c != PORTRAIT_TRANSPARENT_RGB])
    bust = Image.new('P', (96, 80))
    bust.putpalette([v for c in palette for v in c] + [0] * (768 - 3 * len(palette)))
    index = {c: i for i, c in enumerate(palette)}
    bust.putdata([index[px[x, y]] for y in range(80) for x in range(96)])
    return bust


def inject_ch05_visit_faces(campaign, verbose=True):
    """Dress the four reliquary residents' portrait slots with their vendored FE-Repo busts.

    Without this the visits play FACELESS: `village_script` renders a bare `Text_BG`, and a
    message with no `[LoadFace]` draws a boxless, unreadable line -- the same failure ch03's
    grell quote hit. The mugs are Eden/L95's skeleton family, chosen over Glaceo's because they
    read FRIENDLY (these four hand you gifts) and because Sahnar already IS a Glaceo, so hers
    stays the somber face among them.
    """
    vendor = os.path.join(_bust_dir(campaign), 'vendor')
    for vid, (mug, slot, recolor) in sorted(CH05_VISIT_FACES.items()):
        path = os.path.join(vendor, mug)
        if not os.path.isfile(path):
            if verbose:
                print('  (no %s; ch05 %s keeps its vanilla face)' % (mug, vid))
            continue
        tileset, mouth, chibi, pal_bytes = portrait_tool.generate(
            _vendor_mug_to_bust(path, recolor), static_portrait=True)
        base = os.path.join(PORTRAIT_DIR, 'portrait_' + slot)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)
    if verbose:
        print('  ch05 reliquary residents -> %s'
              % ', '.join(sorted(slot for _, slot, _ in CH05_VISIT_FACES.values())))


def _donor_base(campaign, uid, guest_bases=None):
    """The vanilla class/monster a cast member reskins (YAML art.map_sprite.base) -- the
    key that lets us read the sprite's SMS size from the decomp instead of guessing it.
    Cold-open guests have no pcs/npcs YAML, so their base comes from guest_bases
    (PROLOGUE_GUEST_SPRITES) instead of a unit YAML."""
    if guest_bases and uid in guest_bases:
        return guest_bases[uid]
    unit = load_unit(campaign, uid)
    try:
        return unit['art']['map_sprite']['base']
    except (KeyError, TypeError):
        sys.exit('ERROR: %s has map_sprites/%s.png but no art.map_sprite.base in its YAML '
                 '(needed to read the SMS size from the decomp)' % (uid, uid))


def _inject_idle_sprites(campaign, asset_dir, idle, pointer_externs, guest_bases=None,
                         src_override=None):
    """Wait-table slot + GetUnitSMSId override for each idle (<id>.png) asset. `src_override`
    ({uid: path}) supplies a pre-processed sheet (e.g. a faction-tinted unit's role-remapped
    idle) in place of the raw map_sprites/<id>.png."""
    src_override = src_override or {}
    wait_rows, incbin, overrides = [], [], []
    for uid, slot, class_enum, sms in idle:
        raw = src_override.get(uid) or os.path.join(asset_dir, uid + '.png')
        # Frame size from the decomp wait table for the donor base -- not guessed.
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(
            _donor_base(campaign, uid, guest_bases))
        macro, fw, fh, nframes = map_sprite_tool.sheet_info(raw, (dfw, dfh))
        sym = 'unit_icon_wait_manchego_%s_sheet' % uid.replace('-', '_')
        shutil.copyfile(raw, os.path.join(WAIT_GFX_DIR, sym + '.png'))
        wait_rows.append((sms, '\t{0, %s, %s}, /* %d %s */' % (macro, sym, sms, uid)))
        incbin += ['\t.global %s' % sym, '%s:' % sym,
                   '\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"' % sym,
                   '\t.align 2, 0']
        pointer_externs.append('extern char %s[];' % sym)
        overrides.append('\tCHARACTER_%s, %d,' % (slot.upper(), sms))

    for sms, row in wait_rows:
        _write_wait_row(sms, row)
    with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars custom idle sprites (#38) */\n' + '\n'.join(incbin) + '\n')

    # Override table (campaign data) -> needs the CHARACTER_ enum. Non-const so it
    # shares unit_icon_wait_table's kept .data section (the ldscript drops its .rodata).
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        wait_c = f.read()
    if 'constants/characters.h' not in wait_c:
        wait_c = wait_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    wait_c += ('\n/* injected: per-character idle-sprite overrides\n'
               ' * (charId, smsId pairs; 0xFFFF-terminated). Empty == vanilla. */\n'
               'unsigned short gMapSpriteOverride[] = {\n'
               + '\n'.join(overrides) + '\n\t0xFFFF\n};\n')
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(wait_c)

    _inject_sms_override_hook()


def _inject_mu_sprites(mu, pointer_externs):
    """Custom MU sheet + GetMuImg override for each hover/walk asset. `mu` items are
    (uid, slot, class_enum, src_path); src is a committed <id>_mu.png or a synthesized
    glide sheet (see inject_map_sprites)."""
    incbin, overrides = [], []
    for uid, slot, class_enum, src in mu:
        map_sprite_tool.validate_mu_sheet(src)
        sym = 'unit_icon_move_manchego_%s_sheet' % uid.replace('-', '_')
        shutil.copyfile(src, os.path.join(MOVE_GFX_DIR, sym + '.png'))
        incbin += ['\t.global %s' % sym, '%s:' % sym,
                   '\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"' % sym,
                   '\t.align 2, 0']
        pointer_externs.append('extern char %s[];' % sym)
        overrides.append('\t{CHARACTER_%s, %s},' % (slot.upper(), sym))

    with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars custom hover/walk (MU) sprites (#38) */\n'
                + '\n'.join(incbin) + '\n')

    # Override table -> needs the CHARACTER_ enum and the sheet externs. Non-const so it
    # shares unit_icon_move_table's kept .data section.
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        move_c = f.read()
    if 'constants/characters.h' not in move_c:
        move_c = move_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    move_c += ('\n/* injected: per-character MU (hover/walk) sprite overrides\n'
               ' * (charId -> custom sheet; charId 0 terminates). Empty == vanilla. */\n'
               'struct CharMuImg { unsigned short charId; const void * img; };\n'
               'struct CharMuImg gMuImgOverride[] = {\n'
               + '\n'.join(overrides) + '\n\t{0, 0}\n};\n')
    with open(UNIT_ICON_MOVE_C, 'w', encoding='utf-8') as f:
        f.write(move_c)

    _inject_mu_override_hook()


# --- Enemy class reskins (#21) ----------------------------------------------------
# Give an ENEMY a themed overworld sprite without touching its shared vanilla class.
# Reskinning CLASS_SOLDIER/CLASS_FIGHTER directly is campaign-wide (every soldier/fighter
# in every chapter would change); instead we CLONE a base class into an otherwise-unused
# class slot (identical stats + battle anim -> gameplay unchanged) and swap only its MAP
# sprite. Grunts get assigned the cloned class; vanilla classes stay human. Reversible
# and reusable. Unlike the cast path (per-CHARACTER override, bespoke cast palette in its
# own OBJ bank), enemies render their class SMS under the standard ENEMY faction palette,
# so the donor sheet is remapped onto the standard SMS palette index layout (not the cast
# one). The "goblin"/chapter framing lives in campaign YAML; this code is class-agnostic.


def _parse_class_enum_values():
    """CLASS_X -> int value from constants/classes.h (move/class tables index by id-1)."""
    out = {}
    pat = re.compile(r'(CLASS_[A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)')
    with open(CLASSES_H, encoding='utf-8') as f:
        for line in f:
            m = pat.search(line)
            if m:
                out[m.group(1)] = int(m.group(2), 0)
    return out


def _class_field(class_enum, field):
    """Read a numeric field (e.g. SMSId) from a gClassData entry, as written in the C."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    m = re.search(r'\.' + field + r'\s*=\s*(0x[0-9A-Fa-f]+|\d+)', text[bs:be])
    if not m:
        sys.exit('ERROR: .%s not found in gClassData[%s]' % (field, class_enum))
    return int(m.group(1), 0)


def _wait_table_len():
    """Count rows currently in unit_icon_wait_table[] -> the next free SMS id (rows are
    0-indexed by SMS id). Read AFTER inject_map_sprites so the cast rows are included."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    di, ci = _table_close_line(lines, 'unit_icon_wait_table[]')
    return sum(1 for i in range(di + 1, ci) if lines[i].lstrip().startswith('{'))


# How close to the ceiling we let a build get before saying so out loud. Two is the number
# that matters today: ch05's Basil + Sahnar are the last two ids (#225).
SMS_ID_LOW_WATER = 4
_SMS_MASK_BITS = None


def _sms_id_mask_bits():
    """Bit width of the mask the ENGINE applies to every SMS id, read from the decomp:

        src/bmudisp.c:  #define GetInfo(id) (unit_icon_wait_table[(id) & ((1<<7)-1)])

    Read from HEAD, never the working tree -- our injections are build artifacts. Grounding
    the ceiling in the engine that enforces it means a decomp bump moves the guard with it
    instead of leaving a stale literal behind."""
    global _SMS_MASK_BITS
    if _SMS_MASK_BITS is None:
        m = re.search(r'#define\s+GetInfo\(id\)\s*\(unit_icon_wait_table\[\(id\)\s*&\s*'
                      r'\(\(1\s*<<\s*(\d+)\)\s*-\s*1\)\]\)',
                      vanilla_decomp_text('src/bmudisp.c'))
        if not m:
            sys.exit('ERROR: the GetInfo SMS-id mask is not in its expected form in '
                     'src/bmudisp.c -- re-derive the custom SMS id ceiling before building '
                     '(#225), an id past the mask silently renders a VANILLA sprite')
        _SMS_MASK_BITS = int(m.group(1))
    return _SMS_MASK_BITS


def sms_id_max():
    """Highest SMS id the engine can look up without wrapping (127 today)."""
    return (1 << _sms_id_mask_bits()) - 1


def _wait_row_label(row):
    """The unit a generated wait row names, for an error message. Rows carry a trailing
    `// <id> <label>` / `/* <id> <label> */` comment written by the pass that emitted them."""
    m = re.search(r'(?://|/\*)\s*\d+\s+([^*\n]+?)\s*(?:\*/)?$', row.strip())
    return m.group(1).strip() if m else row.strip()


def _move_table_len():
    """Count rows in unit_icon_move_table[] -> the next contiguous class index. The move
    table is a POSITIONAL array indexed by classId-1 (no designated inits), so an appended
    class needs its row at exactly this index for the engine's GetMuImg lookup to line up."""
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    di, ci = _table_close_line(lines, 'unit_icon_move_table[]')
    return sum(1 for i in range(di + 1, ci) if lines[i].lstrip().startswith('{'))


def _move_row_at(class_value):
    """The `{sheet, motion}` pair on the move-table row at index class_value-1 (`// N`)."""
    idx = class_value - 1
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'(\{[^}]+\}),?\s*//\s*%d\s*$' % idx, line)
            if m:
                return m.group(1)
    sys.exit('ERROR: no move-table row at index %d (class %#x)' % (idx, class_value))


def _wait_symbol_at(sms_id):
    """The donor `unit_icon_wait_<Name>_sheet` symbol at row `sms_id` (its `// N` comment),
    and the bare <Name>. The vanilla wait rows are emitted `{..., sym}, // N`."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'(unit_icon_wait_(\w+)_sheet)\}.*//\s*%d\s*$' % sms_id, line)
            if m:
                return m.group(1), m.group(2)
    sys.exit('ERROR: no wait-table row at SMS id %d' % sms_id)


def _move_motion_at(class_value):
    """The motion script symbol on the move-table row at index class_value-1 (`// N`)."""
    idx = class_value - 1
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'\{[^,]+,\s*(\w+)\}.*//\s*%d\s*$' % idx, line)
            if m:
                return m.group(1)
    sys.exit('ERROR: no move-table row at index %d (class %#x)' % (idx, class_value))


def _set_move_row(class_value, sheet_sym, motion_sym):
    """Rewrite the move-table row at index class_value-1 (located by its `// N` comment)."""
    idx = class_value - 1
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        text = f.read()
    pat = re.compile(r'^\t\{[^\n]*\}, // %d$' % idx, re.MULTILINE)
    new, n = pat.subn('\t{%s, %s}, // %d' % (sheet_sym, motion_sym, idx), text, count=1)
    if n == 0:
        sys.exit('ERROR: move-table row // %d not found to reskin' % idx)
    with open(UNIT_ICON_MOVE_C, 'w', encoding='utf-8') as f:
        f.write(new)


def enemy_class_reskins(campaign):
    """The campaign's declared enemy class reskins (campaign.yaml `enemy_class_reskins`),
    as a list of dicts {id, base, slot, sprite}. Empty if none declared."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        return (yaml.safe_load(f) or {}).get('enemy_class_reskins') or []


# --- Faked battle animations (#65) -----------------------------------------------
# Give a unit a custom battle anim from 1-3 static frames + the engine's effects, with
# NO hand-drawn motion. ref_to_battleframe generates the assets (sheets + agbpal + motion.s)
# cloning a donor class's timing; this injects them ADDITIVELY: append a banim_data[] row
# (-> a new animId), then -- so generic/enemy units of the class stay vanilla -- register a
# PRIVATE AnimConf for the CHARACTER in gUnitSpecificBanimConfigs and point its _u25 at it
# (the per-character path; _patch_banim_character_unique routes combat through
# GetBattleAnimationId_WithUnique). No class clone: the unit deploys as its plain vanilla
# class (deploy_class_for). Nothing vanilla is overwritten (donor class + AnimConf
# byte-unchanged). Reversible: the patched files restore each build.

# donor 'clone_from' -> (FE donor class enum, the AnimConf weapon entry to repoint in the
# clone, the cadence the faked motion.s is built with: 'ranged' draw-and-fire / 'melee'
# lunge-and-swing). The cadence is studied from the donor class's own vanilla motion.s.
# clone_from: (donor_class, weapon_type, motion, melee_cadence). `motion` picks the mode
# SHAPE (ranged draw-and-fire vs melee lunge-and-swing); `melee_cadence` picks the per-donor
# sound/FX punctuation within a melee body (ref_to_battleframe._MELEE_CADENCE) -- None for
# ranged donors, which never run a melee body.
BANIM_DONORS = {
    'archer': ('CLASS_ARCHER',       '0x0100 | ITYPE_BOW',   'ranged', None),
    'shaman': ('CLASS_SHAMAN',       '0x0100 | ITYPE_DARK',  'magic',  None),
    'mage':   ('CLASS_MAGE',         '0x0100 | ITYPE_ANIMA', 'magic',  None),
    'pirate': ('CLASS_PIRATE',       '0x0100 | ITYPE_AXE',   'melee',  'axe'),
    'knight': ('CLASS_ARMOR_KNIGHT', '0x0100 | ITYPE_LANCE', 'melee',  'lance'),
    # Pinky (the flier) -- his anim is an IMPORTED N-frame swoop (feditor_to_banim, #90), so
    # `motion`/`cadence` here are unused (the motion.s comes from the .txt); the donor only
    # supplies the AnimConf to clone + the ITYPE_LANCE slot to repoint for her per-character
    # _u25. A flier's hover-and-dive can't be faked from 3 static poses (decisions.md).
    'pegasus': ('CLASS_PEGASUS_KNIGHT', '0x0100 | ITYPE_LANCE', 'melee', 'lance'),
    # Sclorbo (the army's first healer, Priest->Bishop). Cloning the BISHOP AnimConf gives
    # BOTH a STAFF slot (drives the MVP: heal-cast + defense as a Priest) and a LIGHT slot
    # (the post-promotion attack). Both slots repoint to his ONE custom animId; call_spell_anim
    # resolves heal-efx vs light-efx from the equipped item at runtime. Basil (#25) reuses this.
    # ITYPE_ITEM joined the list on the #25 review: the Bishop AnimConf carries five slots
    # (STAFF/ANIMA/LIGHT/DARK/ITEM) and leaving ITEM vanilla means a healer holding no staff --
    # both spent, only a Vulnerary left -- renders as a HUMAN BISHOP in the close-up. That is
    # the cavalier row's rule ("every slot left vanilla is a slot where the wolf renders as a
    # man on a horse", #206) applied to the class that needed it next. ANIMA/DARK stay vanilla
    # deliberately: neither this line's Priest nor its Bishop promotion can equip those, so a
    # repoint there would be dead weight, not coverage.
    'bishop': ('CLASS_BISHOP', ['0x0100 | ITYPE_STAFF', '0x0100 | ITYPE_LIGHT',
                                '0x0100 | ITYPE_ITEM'], 'magic', None),
    # Lupin (the beast-cavalier) -- his anim is an IMPORTED N-frame POUNCE (feditor_to_banim, #90),
    # so `motion`/`cadence` are unused (the .txt owns them, and its cadence is read off FE8's own
    # wolf `banim_mdg_at1`, not off this donor). The donor supplies the AnimConf to clone; ALL
    # THREE of the Cavalier's weapon slots are repointed, because every slot left vanilla is a
    # slot where the wolf renders as A MAN ON A HORSE -- which is the whole defect in #206.
    # ITYPE_ITEM is the unarmed/item entry, reachable whenever he holds no weapon. Baxby (#206's
    # other half, the axe-beak) is the same class and reuses this row.
    'cavalier': ('CLASS_CAVALIER', ['0x0100 | ITYPE_SWORD', '0x0100 | ITYPE_LANCE',
                                    '0x0100 | ITYPE_ITEM'], 'melee', 'lance'),
    # Sahnar (the risen duelist, #25) -- an IMPORTED 12-mode Specter script (feditor_to_banim),
    # so `motion`/`cadence` go unused for HER: the .txt owns the cadence and the sound codes.
    # They are still filled in properly rather than left None, because the row is the donor for
    # the class, not for one unit -- and the 'sword' cadence it names is read off FE8's own
    # banim_myrm_sw1 (ref_to_battleframe._MELEE_CADENCE). BOTH of the donor's slots are
    # repointed: the Myrmidon AnimConf is SWORD + ITEM, and ITYPE_ITEM is the UNARMED entry --
    # reachable the moment both her swords break and she is carrying only a Vulnerary. Left
    # vanilla it draws a HUMAN MYRMIDON instead of the revenant, which is the cavalier row's
    # #206 defect exactly. Caught on review, not in play (#25).
    'myrmidon': ('CLASS_MYRMIDON', ['0x0100 | ITYPE_SWORD', '0x0100 | ITYPE_ITEM'],
                 'melee', 'sword'),
}


def build_unit_battle_anim(cfg, anim_dir, abbr, motion, cadence):
    """Build a unit's battle-anim assets, returning {"sheets", "pal", "motion_s"}.

    Two sources, ONE asset shape (so the injector's binding is identical either way):
    - `import: {txt, frames_dir}` -> a real N-frame FE-native animation transcribed by
      feditor_to_banim (#90). Used when 3 faked poses can't carry the motion -- e.g. Pinky's
      flier swoop (launch/apex/dive/return). The `.txt` owns the cadence; each frame's canvas
      position is the on-screen motion. This is the enemy #90 path bound per-CHARACTER, not
      per-class.
    - else `frames: [...]` -> the faked 3-pose generator (ref_to_battleframe, #65), whose mode
      bodies are built from the donor's `motion`/`cadence`.
    """
    imp = cfg.get('import')
    if imp:
        txt = os.path.join(anim_dir, imp['txt'])
        frames_dir = os.path.join(anim_dir, imp.get('frames_dir')
                                  or os.path.dirname(imp['txt']))
        return feditor_to_banim.build_import(abbr, txt, frames_dir)
    from PIL import Image
    frame_imgs = [Image.open(os.path.join(anim_dir, p)).convert('RGBA')
                  for p in cfg['frames']]
    palette = _banim_palette(frame_imgs)
    return ref_to_battleframe.build_battle_anim(abbr, frame_imgs, palette, motion=motion,
                                                cadence=cadence or 'axe')


def banim_append_row(text, abbr):
    """Append a banim_data[] row for `abbr`; return (new_text, anim_id).

    anim_id = the count of existing rows (the table is appended-to, so the donor rows are
    byte-unchanged and `banim_number = sizeof(...)` picks up the growth automatically)."""
    anim_id = text.count('\t{"')
    row = ('\t{"%s", &banim_%s_modes_bin, &banim_%s_motion_o, &banim_%s_oam_r_bin, '
           '&banim_%s_oam_l_bin, &banim_%s_agbpal}, // 0x%X (#65)\n'
           % (abbr, abbr, abbr, abbr, abbr, abbr, anim_id))
    close = text.rindex('};')
    return text[:close] + row + text[close:], anim_id


def banim_unique_append(text, conf_sym):
    """Append `conf_sym` to gUnitSpecificBanimConfigs[] (#65 M-B); return (text, index).

    The character-unique path (no class slot): a unit's AnimConf is registered here and the
    character's _u25 points at the returned index. Self-sizing, so existing rows are
    byte-unchanged. index = the count of existing entries (each carries a trailing comma)."""
    marker = 'gUnitSpecificBanimConfigs[] = {'
    bs = text.index(marker) + len(marker)
    be = text.index('};', bs)
    block = text[bs:be]
    index = block.count(',')
    return text[:bs] + block.rstrip() + '\n    %s,\n' % conf_sym + text[be:], index


def banim_spell_palette_tint_append(text, rows):
    """Append the campaign-declared character/weapon spell-tint rows once."""
    character_include = '#include "constants/characters.h"\n'
    if character_include not in text:
        anchor = '#include "constants/items.h"\n'
        if anchor not in text:
            raise ValueError('battle-animation data file is missing constants/items.h include')
        text = text.replace(anchor, anchor + character_include, 1)
    marker = 'gBanimSpellPaletteTints[]'
    if marker in text:
        return text
    block = '\nCONST_DATA struct BanimSpellPaletteTint %s = {\n' % marker
    for character, weapon_type, tint in rows:
        block += '    { %s, %s, %s },\n' % (character, weapon_type, tint)
    block += '    { 0, 0, BANIM_SPELL_TINT_NONE },\n};\n'
    return text + block


def banim_charge_flash_append(text, rows):
    """Append the campaign-declared per-caster charge-flash rows once (#183, #191 waveform).

    Each row is (character, weapon_type, target_bgr555, waveform) -- the caster's own sprite
    pulses toward `target_bgr555` on the wind-up beat, using LUT `waveform` (0 = pulse, the
    existing 3-throb throb; 1 = build, a single slow swell). The colour rides as a raw BGR555
    u16 so the engine blends toward any hue without a per-colour enum. Zero-character row
    terminates."""
    character_include = '#include "constants/characters.h"\n'
    if character_include not in text:
        anchor = '#include "constants/items.h"\n'
        if anchor not in text:
            raise ValueError('battle-animation data file is missing constants/items.h include')
        text = text.replace(anchor, anchor + character_include, 1)
    marker = 'gMSChargeFlashes[]'
    if marker in text:
        return text
    block = '\nCONST_DATA struct BanimChargeFlash %s = {\n' % marker
    for character, weapon_type, target, waveform in rows:
        block += '    { %s, %s, %s, %d },\n' % (character, weapon_type, target, waveform)
    block += '    { 0, 0, 0, 0 },\n};\n'
    return text + block


def banim_set_char_u25(block, index):
    """Set a character block's `._u25 = { index, index }` (#65 M-B), inserting after
    `.number` if absent, overwriting in place if already present (both promote states)."""
    val = '._u25 = { %d, %d },' % (index, index)
    if '._u25' in block:
        return re.sub(r'\._u25 = \{[^}]*\},', val, block)
    m = re.search(r'\n([ \t]*)\.number = [^\n]*\n', block)
    return block[:m.end()] + m.group(1) + val + '\n' + block[m.end():]


def banim_repoint_conf(text, conf_sym, wtype_literal, new_index):
    """In AnimConf `conf_sym`, set the `.index` of the entry matching `wtype_literal`."""
    bs, be = _find_brace_block(text, '%s[] =' % conf_sym, BANIMCONF_C)
    block = text[bs:be]
    pat = re.compile(r'(\.wtype\s*=\s*' + re.escape(wtype_literal) +
                     r'\s*,\s*\.index\s*=\s*)(0x[0-9A-Fa-f]+|\d+)')
    new_block, n = pat.subn(lambda m: '%s0x%X' % (m.group(1), new_index), block, count=1)
    if n == 0:
        sys.exit('ERROR: banim repoint: wtype %r not found in %s' % (wtype_literal, conf_sym))
    return text[:bs] + new_block + text[be:]


def banim_clone_conf(text, src_sym, new_sym, wtype_literal, new_index):
    """Append a COPY of AnimConf `src_sym` as `new_sym`, with the `wtype_literal` entry's
    `.index` set to `new_index`. `src_sym` is left byte-unchanged (the donor class keeps the
    vanilla anim). Returns the new text (declaration appended)."""
    bs, be = _find_brace_block(text, '%s[] =' % src_sym, BANIMCONF_C)
    block = text[bs:be]
    pat = re.compile(r'(\.wtype\s*=\s*' + re.escape(wtype_literal) +
                     r'\s*,\s*\.index\s*=\s*)(0x[0-9A-Fa-f]+|\d+)')
    new_block, n = pat.subn(lambda m: '%s0x%X' % (m.group(1), new_index), block, count=1)
    if n == 0:
        sys.exit('ERROR: banim clone: wtype %r not found in %s' % (wtype_literal, src_sym))
    return text + '\nCONST_DATA struct BattleAnimDef %s[] = %s;\n' % (new_sym, new_block)


def _banim_palette(frame_imgs):
    """A <=16-colour palette for the frames: index 0 transparent + each opaque colour."""
    pal = [(0, 0, 0)]
    for im in frame_imgs:
        for cnt, rgba in im.getcolors(1 << 24):
            rgb = rgba[:3]
            # OBJ palette index 0 is transparent even when its BGR555 colour is black.
            # Retain an opaque black as a duplicate at index 1+ rather than mapping it
            # to that transparent slot.
            if rgba[3] > 0 and (rgb not in pal or (rgb == pal[0] and pal.count(rgb) == 1)):
                pal.append(rgb)
    return pal


def units_with_battle_anim(campaign):
    """(unit_id, unit) for every pc/npc YAML carrying a `battle_anim:` block."""
    out = []
    for sub in ('pcs', 'npcs'):
        d = os.path.join(REPO, 'campaigns', campaign, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.yaml'):
                continue
            with open(os.path.join(d, fn), encoding='utf-8') as f:
                u = yaml.safe_load(f)
            if u and u.get('battle_anim'):
                out.append((u.get('id', fn[:-5]), u))
    return out


def battle_spell_palette_tints(campaign):
    """(character enum, weapon type, tint enum) rows declared by battle_anim YAML.

    A block declares either a single `weapon_type:` (one row -- Marty/Rootis, unchanged) or a
    `weapon_types:` LIST (one row per type -- Sclorbo's staff + light both cyan). If neither key
    is present, auto-emit a row for each of the donor's bound weapon types."""
    tint_enums = {
        'green': 'BANIM_SPELL_TINT_GREEN',
        'blue': 'BANIM_SPELL_TINT_BLUE',
        'cyan': 'BANIM_SPELL_TINT_CYAN',   # Sclorbo's flame cyan -- bright equal G+B (#191)
        'gold': 'BANIM_SPELL_TINT_GOLD',   # Basil's goodberry gold -- cyan's mirror (#25)
    }
    type_enums = {
        'dark': 'ITYPE_DARK',
        'anima': 'ITYPE_ANIMA',
        'staff': 'ITYPE_STAFF',
        'light': 'ITYPE_LIGHT',
    }
    out = []
    for uid, unit in units_with_battle_anim(campaign):
        tint = unit['battle_anim'].get('spell_palette_tint')
        if not tint:
            continue
        try:
            if 'weapon_types' in tint:
                wtypes = [type_enums[w] for w in tint['weapon_types']]
            elif 'weapon_type' in tint:
                wtypes = [type_enums[tint['weapon_type']]]
            else:
                donor = BANIM_DONORS[unit['battle_anim']['clone_from']]
                donor_wtypes = donor[1] if isinstance(donor[1], list) else [donor[1]]
                wtypes = [w.split('|')[-1].strip() for w in donor_wtypes]
            color = tint_enums[tint['color']]
            slot = PORTRAIT_MAP[uid]
        except KeyError as e:
            sys.exit('ERROR: battle_anim %s spell_palette_tint: unsupported %s' %
                     (uid, e))
        for weapon_type in wtypes:
            out.append((char_symbol(slot), weapon_type, color))
    return out


# Per-caster charge-flash colours (#183): the sprite pulses toward this hue on the wind-up
# beat. Each caster's identity colour; blended additively (a wash), so any hue works.
CHARGE_FLASH_RGB = {
    'blue':   (120, 205, 255),   # ice (Rootis)
    'green':  (110, 255, 120),   # (Marty)
    'purple': (200, 120, 255),   # (Meesmickle)
    'cyan':   (31, 219, 219),    # flame cyan (Sclorbo, #191, Nicolas-approved -> BGR555 0x6F63)
    'gold':   (255, 205, 70),    # goodberry gold (Basil, #25) -- warm, and far enough off
                                 # Sclorbo's cyan that the two healers never read alike
}


def charge_flash_target(color):
    """A named charge-flash colour -> its BGR555 hex string (the blend target)."""
    r, g, b = CHARGE_FLASH_RGB[color]
    return '0x%04X' % ((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))


def battle_charge_flashes(campaign):
    """(character, weapon_type, target_bgr555, waveform) rows from battle_anim `charge_flash`
    blocks. waveform: 0 = pulse (default, the existing 3-throb LUT), 1 = build (a single slow
    swell), from `charge_flash.waveform: 'pulse'|'build'`.

    The weapon type is the caster's DONOR weapon type (the flash arms for whatever tome the
    faked anim is bound to), so a `charge_flash` block only needs a colour. A donor's weapon
    type may be a single string (one row) or a LIST (e.g. Sclorbo's bishop donor -- staff +
    light) -- emit one row per weapon type so the glow arms on every bound tome/staff."""
    waveform_ids = {'pulse': 0, 'build': 1}
    out = []
    for uid, unit in units_with_battle_anim(campaign):
        flash = unit['battle_anim'].get('charge_flash')
        if not flash:
            continue
        try:
            donor = BANIM_DONORS[unit['battle_anim']['clone_from']]
            target = charge_flash_target(flash['color'])
            waveform = waveform_ids[flash.get('waveform', 'pulse')]
            slot = PORTRAIT_MAP[uid]
        except KeyError as e:
            sys.exit('ERROR: battle_anim %s charge_flash: unsupported %s' % (uid, e))
        donor_wtypes = donor[1] if isinstance(donor[1], list) else [donor[1]]
        for wtype_literal in donor_wtypes:
            weapon_type = wtype_literal.split('|')[-1].strip()   # '0x0100 | ITYPE_ANIMA' -> 'ITYPE_ANIMA'
            out.append((char_symbol(slot), weapon_type, target, waveform))
    return out


def inject_battle_anims(campaign, verbose=True):
    """Generate + inject each unit's faked battle animation (additive donor-prime, #65).

    ADDING A UNIT (the repeatable how): give its YAML a `battle_anim:` block --
        clone_from: archer                  # donor class: timing/effects/modes + the weapon slot
        abbr: <stem>                        # banim asset stem (<=12 chars)
        frames: [<unit>/ready.png, <unit>/windup.png, <unit>/peak.png]  # 1-3, Ready->Windup->Peak
        # (+ optional motion/cadence per BANIM_DONORS; no class key -- see below)
    Frames: BOX-descale the hi-res (e.g. 1920x1080) source poses onto a ~88x64 canvas with a COMMON
    feet-anchor + a protected ~15-colour palette. NEVER re-shrink an already-small frame (non-integer
    re-shrink looks muddy) -- to rescale a unit, re-descale from the hi-res master.

    This APPENDS a banim_data[] row (table self-sizes) and registers a PRIVATE AnimConf for the
    CHARACTER (gUnitSpecificBanimConfigs + the character's _u25, routed by
    _patch_banim_character_unique) -- the donor class, its AnimConf, and every generic/enemy unit
    of it stay byte-vanilla, and the unit deploys as its PLAIN vanilla class (deploy_class_for;
    the earlier clone-class approach is retired). Stats ride STAT_DONOR/
    BASE_DONOR/GROWTH_DONOR; PORTRAIT_MAP ties the unit id -> its vanilla character slot.

    !! OFF-BY-ONE: the private AnimConf `.index` MUST be `anim_id + 1` (GetBattleAnimationId returns
       idx - 1). Get it wrong and a PURPLE DRAGON renders instead of the unit.
    Decisions/rationale: decisions.md (Art & Audio, the per-character _u25 call).
    """
    units = units_with_battle_anim(campaign)
    if not units:
        if verbose:
            print('  (no battle_anim blocks declared)')
        return
    anim_dir = os.path.join(REPO, 'campaigns', campaign, 'battle_anims')
    os.makedirs(BANIM_DATA_DIR, exist_ok=True)
    os.makedirs(BANIM_GFX_DIR, exist_ok=True)

    for uid, unit in units:
        cfg = unit['battle_anim']
        clone_from = cfg['clone_from']
        if clone_from not in BANIM_DONORS:
            sys.exit('ERROR: battle_anim %s: unsupported clone_from %r' % (uid, clone_from))
        donor_class, wtype, motion, cadence = BANIM_DONORS[clone_from]
        motion = cfg.get('motion', motion)            # YAML may override the donor default
        cadence = cfg.get('cadence', cadence)         # ...and its melee cadence
        abbr = cfg.get('abbr') or (uid.replace('-', '').replace('prof', '')[:5] + '_ar1')
        res = build_unit_battle_anim(cfg, anim_dir, abbr, motion, cadence)

        # 1. assets into the decomp (motion.s, per-frame sheet PNGs, agbpal blob)
        with open(os.path.join(BANIM_DATA_DIR, 'banim_%s_motion.s' % abbr), 'w',
                  encoding='utf-8') as f:
            f.write(res['motion_s'])
        for i, sheet in enumerate(res['sheets']):
            sheet.save(os.path.join(BANIM_GFX_DIR, 'banim_%s_sheet_%d.png' % (abbr, i)))
        with open(os.path.join(BANIM_GFX_DIR, 'banim_%s.agbpal' % abbr), 'wb') as f:
            f.write(res['pal'])

        # 2. linker block (sheets, palette, oam, script, modes), in build order
        block = (['graphics/banim/banim_%s_sheet_%d.4bpp.lz' % (abbr, i)
                  for i in range(len(res['sheets']))]
                 + ['graphics/banim/banim_%s.agbpal.lz' % abbr,
                    'data/banim/banim_%s_oam_l.bin.lz' % abbr,
                    'data/banim/banim_%s_oam_r.bin.lz' % abbr,
                    'data/banim/banim_%s_motion.o|.data.script>lz' % abbr,
                    'data/banim/banim_%s_modes.bin' % abbr])
        with open(BANIM_LINKER, 'a', encoding='utf-8') as f:
            f.write('\n# Manchego Stars faked battle anim (#65): %s\n' % uid)
            f.write('\n'.join(block) + '\n')

        # 3. banim_data[] row -> new animId, plus its pointer externs
        with open(BANIM_DATA_C, encoding='utf-8') as f:
            text = f.read()
        text, anim_id = banim_append_row(text, abbr)
        with open(BANIM_DATA_C, 'w', encoding='utf-8') as f:
            f.write(text)
        with open(BANIM_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('// battle animation 0x%X (Manchego Stars #65: %s)\n' % (anim_id, uid))
            for sym, ty in [('modes_bin', 'int'), ('motion_o', 'char'),
                            ('oam_r_bin', 'char'), ('oam_l_bin', 'char'),
                            ('agbpal', 'char')]:
                f.write('extern %s banim_%s_%s;\n' % (ty, abbr, sym))

        # 4. CHARACTER-UNIQUE (no class slot, #65 M-B): build the unit's private AnimConf,
        #    register it in the per-character table, and point the character's _u25 at it.
        #    The donor class + every generic/enemy unit of it stay byte-vanilla; only THIS
        #    named character animates custom (the _patch_banim_character_unique engine hook
        #    routes combat through GetBattleAnimationId_WithUnique, which reads _u25). Scales
        #    to every PC + named boss -- bounded by the anim table, not the ~3 class slots.
        new_conf = 'AnimConf_%s' % abbr
        src_conf = _class_field_symbol(donor_class, 'pBattleAnimDef')  # e.g. AnimConf_088AF150
        # 4a. a private AnimConf = copy of the donor's, with the weapon entry -> new animId.
        #     NOTE: AnimConf `.index` is animId+1 -- GetBattleAnimationId returns `idx - 1`
        #     (vanilla archer bow .index 0x26 -> animId 0x25). So encode anim_id + 1.
        with open(BANIMCONF_C, encoding='utf-8') as f:
            conf = f.read()
        wtypes = wtype if isinstance(wtype, list) else [wtype]
        conf = banim_clone_conf(conf, src_conf, new_conf, wtypes[0], anim_id + 1)
        for wt in wtypes[1:]:
            conf = banim_repoint_conf(conf, new_conf, wt, anim_id + 1)
        with open(BANIMCONF_C, 'w', encoding='utf-8') as f:
            f.write(conf)
        with open(BANIM_EKRBATTLE_H, 'a', encoding='utf-8') as f:
            f.write('extern CONST_DATA struct BattleAnimDef %s[]; /* Manchego Stars #65 */\n'
                    % new_conf)
        # 4b. register the AnimConf in gUnitSpecificBanimConfigs[] -> its table index.
        with open(BANIMCONFUNK_C, encoding='utf-8') as f:
            unk = f.read()
        unk, u25 = banim_unique_append(unk, new_conf)
        with open(BANIMCONFUNK_C, 'w', encoding='utf-8') as f:
            f.write(unk)
        # 4c. point the character's _u25 (both promote states) at that index. The PC rides a
        #     vanilla character slot (PORTRAIT_MAP); the engine hook makes combat consult it.
        slot = PORTRAIT_MAP.get(uid)
        if not slot:
            sys.exit('ERROR: battle_anim %s: no PORTRAIT_MAP character slot for _u25' % uid)
        marker = '[CHARACTER_%s - 1]' % slot.upper()
        with open(CHARACTERS_C, encoding='utf-8') as f:
            ctext = f.read()
        cs, ce = _find_brace_block(ctext, marker, CHARACTERS_C)
        ctext = ctext[:cs] + banim_set_char_u25(ctext[cs:ce], u25) + ctext[ce:]
        with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
            f.write(ctext)

        if verbose:
            print('  %-14s = banim %s (animId 0x%X); _u25[%d] -> %s on char %s (%s)'
                  % (uid, abbr, anim_id, u25, new_conf, slot, wtype))

    tint_rows = battle_spell_palette_tints(campaign)
    if tint_rows:
        with open(BANIMCONFUNK_C, encoding='utf-8') as f:
            tint_text = f.read()
        with open(BANIMCONFUNK_C, 'w', encoding='utf-8') as f:
            f.write(banim_spell_palette_tint_append(tint_text, tint_rows))
        if verbose:
            print('  spell palette tints: %d character/weapon row(s)' % len(tint_rows))

    flash_rows = battle_charge_flashes(campaign)
    if flash_rows:
        with open(BANIMCONFUNK_C, encoding='utf-8') as f:
            flash_text = f.read()
        with open(BANIMCONFUNK_C, 'w', encoding='utf-8') as f:
            f.write(banim_charge_flash_append(flash_text, flash_rows))
        if verbose:
            print('  charge flashes (#183): %d caster(s) pulse on the wind-up beat' % len(flash_rows))


def _class_field_symbol(class_enum, field):
    """Read a symbol-valued field (e.g. .pBattleAnimDef = AnimConf_X) from gClassData."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    m = re.search(r'\.' + field + r'\s*=\s*(\w+)', text[bs:be])
    if not m:
        sys.exit('ERROR: .%s symbol not found in gClassData[%s]' % (field, class_enum))
    return m.group(1)


def set_class_field_symbol(text, class_enum, field, symbol):
    """Repoint a symbol-valued class field (e.g. .pBattleAnimDef = AnimConf_X) IN PLACE,
    within only [class_enum - 1]'s block. Returns the new text; errors if the field is
    absent. The class-level enemy battle-anim path (#90): a reskin clone's cloned body carries
    the base class's .pBattleAnimDef; this repoints it at the imported class-level AnimConf,
    leaving every sibling class (including the vanilla donor) byte-unchanged."""
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    block = text[bs:be]
    new, n = re.subn(r'(\.%s\s*=\s*)\w+' % field, r'\g<1>' + symbol, block, count=1)
    if n == 0:
        sys.exit('ERROR: .%s not found in gClassData[%s]' % (field, class_enum))
    return text[:bs] + new + text[be:]


def class_enum_insert(text, name, value):
    """Insert `NAME = 0xVALUE,` into the class enum after the last numeric-valued CLASS_
    entry (idempotent). Extends the vanilla 0x7F tail so an enemy reskin can ride a class
    slot beyond the three ballista-empties (#23). The value-less `= CLASS_OBSTACLE` alias
    tail is skipped -- we anchor on the last real id so the enum reader picks up the new
    constant. Class ids are a u8 with 0x80-0xFF free and gClassData is unsized (no count
    cap), so appending is safe (see decisions.md / HANDOFF #23)."""
    if re.search(r'\b' + re.escape(name) + r'\s*=', text):
        return text
    anchors = list(re.finditer(r'^([ \t]*)CLASS_[A-Z0-9_]+\s*=\s*(?:0x[0-9A-Fa-f]+|\d+)\s*,',
                               text, re.M))
    if not anchors:
        sys.exit('ERROR: class_enum_insert: no numeric CLASS_ entry to anchor on')
    m = anchors[-1]
    eol = text.find('\n', m.end())
    if eol < 0:
        eol = len(text)
    return text[:eol] + '\n%s%s = 0x%02X,' % (m.group(1), name, value) + text[eol:]


def classdata_append_clone(text, base_enum, new_enum):
    """Append a clone of gClassData[base_enum-1] as a NEW [new_enum-1] entry (idempotent).
    The clone carries the base body verbatim (stats + battle anim ride along); the reskin
    loop repoints .number/.SMSId afterward via the existing _set_field path. Used when a
    reskin's `slot` is a freshly-appended class id rather than a vanilla ballista-empty."""
    designator = '[%s - 1]' % new_enum
    if designator in text:
        return text
    bs, be = _find_brace_block(text, '[%s - 1]' % base_enum, CLASSES_C)
    body = text[bs:be]
    _, arr_e = _find_brace_block(text, 'gClassData[] =', CLASSES_C)
    entry = '    %s = %s,\n' % (designator, body)
    return text[:arr_e - 1] + entry + text[arr_e - 1:]


def _append_new_reskin_slots(reskins, verbose=True):
    """Append any reskin `slot`s declared with a `slot_id` (a fresh class id past 0x7F)
    that don't yet exist as classes -- extend the enum + clone the base into gClassData so
    the per-reskin clone loop can then ride the new slot (#23: the Lizardzerker, once the
    three ballista-empties are used up). Idempotent (build restores classes.h/.c each run);
    a reskin whose `slot` is already a real class (vanilla ballista-empty) is left alone."""
    values = _parse_class_enum_values()
    header = cdata = None
    for rk in reskins:
        if rk.get('slot_id') is None or rk['slot'] in values:
            continue
        slot, base, val = rk['slot'], rk['base'], int(str(rk['slot_id']), 0)
        if header is None:
            header = open(CLASSES_H, encoding='utf-8').read()
            cdata = open(CLASSES_C, encoding='utf-8').read()
        header = class_enum_insert(header, slot, val)
        cdata = classdata_append_clone(cdata, base, slot)
        # The positional (class-indexed) move table needs a contiguous row at index val-1
        # so the reskin loop's _set_move_row can rewrite it; fill any gap with the base's
        # row (never deployed) and keep the array dense for the engine's GetMuImg lookup.
        cur = _move_table_len()
        if val > cur:
            base_row = _move_row_at(values[base])
            _append_table_rows(UNIT_ICON_MOVE_C, 'unit_icon_move_table[]',
                               ['\t%s, // %d' % (base_row, i) for i in range(cur, val)])
        values[slot] = val
        if verbose:
            print('  %-16s = append class %s = 0x%X (clone of %s)'
                  % (rk['id'], slot, val, base))
    if header is not None:
        with open(CLASSES_H, 'w', encoding='utf-8') as f:
            f.write(header)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(cdata)


def inject_enemy_class_reskins(campaign, verbose=True):
    """Clone each declared base class into its unused slot with a custom MAP sprite only.

    Per reskin (campaign.yaml): clone gClassData[base-1] into [slot-1] (full copy so the
    battle anim/stats ride along -> combat unchanged), repoint .number/.SMSId; append the
    reskin's idle sheet as a new wait-table row at that SMSId; repoint the move-table row
    at slot-1 to the reskin's walk sheet (reusing the base class's motion script). Sheets
    are remapped onto the BASE class's standard SMS palette (map_sprite_tool) so the enemy
    faction palette colours them. Sprites are de-duped: reskins that share a `sprite` share
    one wait row / move sheet (one goblin sprite, two classes)."""
    reskins = enemy_class_reskins(campaign)
    if not reskins:
        if verbose:
            print('  (no enemy_class_reskins declared)')
        return
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    # Append any freshly-declared class slots (slot_id present) before resolving enum
    # values, so a reskin can ride a slot beyond the three vanilla ballista-empties (#23).
    _append_new_reskin_slots(reskins, verbose)
    values = _parse_class_enum_values()
    pointer_externs = []
    sprite_sms = {}        # sprite stem -> SMS id of its (shared) wait row
    sprite_move_sym = {}   # sprite stem -> move-sheet symbol

    for rk in reskins:
        base, slot, sprite = rk['base'], rk['slot'], rk['sprite']
        for key in ('base', 'slot'):
            if rk[key] not in values:
                sys.exit('ERROR: enemy_class_reskins %s: unknown class %r' % (rk['id'], rk[key]))

        # Donor SMS palette + geometry come from the base class's vanilla wait sheet.
        base_sms = _class_field(base, 'SMSId')
        donor_sym, donor_name = _wait_symbol_at(base_sms)
        donor_png = os.path.join(WAIT_GFX_DIR, donor_sym + '.png')

        # Graphics once per unique sprite (shared across reskins of the same sprite).
        if sprite not in sprite_sms:
            stand = os.path.join(asset_dir, sprite + '.png')
            walk = os.path.join(asset_dir, sprite + '_mu.png')
            for p in (stand, walk):
                if not os.path.isfile(p):
                    sys.exit('ERROR: enemy_class_reskins %s: missing map_sprites/%s'
                             % (rk['id'], os.path.basename(p)))
            sym = sprite.replace('-', '_')
            wait_sym = 'unit_icon_wait_manchego_%s_sheet' % sym
            move_sym = 'unit_icon_move_manchego_%s_sheet' % sym
            # Remap onto the base class's standard SMS palette (enemy faction recolours it).
            map_sprite_tool.remap_sms_palette(stand, donor_png,
                                              os.path.join(WAIT_GFX_DIR, wait_sym + '.png'))
            map_sprite_tool.remap_sms_palette(walk, donor_png,
                                              os.path.join(MOVE_GFX_DIR, move_sym + '.png'))
            # Idle frame geometry: a `frame` override (e.g. "16x32") when the sprite is a
            # different size class than the base (the Fire Imp is a tall 16x32 sprite on a
            # 16x16 soldier/fighter -- the engine draws it via the wait-row size flag);
            # else the base class's own SMS size.
            if rk.get('frame'):
                dfw, dfh = (int(v) for v in str(rk['frame']).lower().split('x'))
            else:
                _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor_name)
            macro, fw, fh, _ = map_sprite_tool.sheet_info(
                os.path.join(WAIT_GFX_DIR, wait_sym + '.png'), (dfw, dfh))
            map_sprite_tool.validate_mu_sheet(os.path.join(MOVE_GFX_DIR, move_sym + '.png'))

            sms_id = claim_sms_id()
            _write_wait_row(sms_id,
                '\t{0, %s, %s}, // %d %s (reskin)' % (macro, wait_sym, sms_id, sprite))
            with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
                f.write('\n/* Manchego Stars enemy class reskin idle (#21) */\n'
                        '\t.global %s\n%s:\n'
                        '\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n\t.align 2, 0\n'
                        % (wait_sym, wait_sym, wait_sym))
            with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
                f.write('\n/* Manchego Stars enemy class reskin walk (#21) */\n'
                        '\t.global %s\n%s:\n'
                        '\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n\t.align 2, 0\n'
                        % (move_sym, move_sym, move_sym))
            pointer_externs += ['extern char %s[];' % wait_sym, 'extern char %s[];' % move_sym]
            sprite_sms[sprite] = sms_id
            sprite_move_sym[sprite] = move_sym

        # Clone base class -> slot (full body), repoint number + SMSId.
        with open(CLASSES_C, encoding='utf-8') as f:
            text = f.read()
        bs, be = _find_brace_block(text, '[%s - 1]' % base, CLASSES_C)
        body = text[bs:be]
        body = _set_field(body, 'number', slot, CLASSES_C, base)
        body = _set_field(body, 'SMSId', '0x%x' % sprite_sms[sprite], CLASSES_C, base)
        text = _replace_brace_block(text, '[%s - 1]' % slot, body, CLASSES_C)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(text)

        # Repoint the cloned class's move-table row to the reskin walk sheet, reusing the
        # base class's motion script (so it animates like the base class).
        _set_move_row(values[slot], sprite_move_sym[sprite], _move_motion_at(values[base]))

        if verbose:
            print('  %-16s = clone %s -> %s (SMS %d, sprite %s)'
                  % (rk['id'], base, slot, sprite_sms[sprite], sprite))

    if pointer_externs:
        with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars enemy class reskin sprites (#21) */\n'
                    + '\n'.join(pointer_externs) + '\n')


# --- Class-level imported battle animations (#90) --------------------------------
# Reskinned enemy CLASSES carry a custom map sprite (inject_enemy_class_reskins) but animate
# as their vanilla donor (Brigand/Soldier/...) in the battle close-up. This imports a real
# FE-native community animation (feditor_to_banim) and binds it at the CLASS via
# ClassData.pBattleAnimDef -- the generic-enemy analogue of the PC per-character _u25 path.
# Additive + reversible: the imported anims append banim_data[] rows; a PRIVATE class-level
# AnimConf (a clone of the donor's, weapon entries repointed) is appended and the reskin clone
# class's .pBattleAnimDef points at it. The donor class + its AnimConf stay byte-vanilla.


# Named enemy-faction palette passes a `battle_anim: {recolor: <name>}` may select. Kept a
# registry (not free-form) so the campaign YAML stays declarative and the transforms are tested.
BANIM_RECOLORS = {
    'enemy_red': feditor_to_banim.enemy_red_recolor,
}


def _write_imported_banim_assets(abbr, res, uid):
    """Write one imported anim's assets into the decomp and register it: motion.s + per-frame
    sheet PNGs + agbpal (step 1), the linker block (2), and the banim_data[] row + pointer
    externs (3). Returns the new animId. Shared shape with the faked path (inject_battle_anims
    steps 1-3); only the asset SOURCE differs (transcribed FEditor vs faked 3-pose)."""
    with open(os.path.join(BANIM_DATA_DIR, 'banim_%s_motion.s' % abbr), 'w',
              encoding='utf-8') as f:
        f.write(res['motion_s'])
    for i, sheet in enumerate(res['sheets']):
        sheet.save(os.path.join(BANIM_GFX_DIR, 'banim_%s_sheet_%d.png' % (abbr, i)))
    with open(os.path.join(BANIM_GFX_DIR, 'banim_%s.agbpal' % abbr), 'wb') as f:
        f.write(res['pal'])

    block = (['graphics/banim/banim_%s_sheet_%d.4bpp.lz' % (abbr, i)
              for i in range(len(res['sheets']))]
             + ['graphics/banim/banim_%s.agbpal.lz' % abbr,
                'data/banim/banim_%s_oam_l.bin.lz' % abbr,
                'data/banim/banim_%s_oam_r.bin.lz' % abbr,
                'data/banim/banim_%s_motion.o|.data.script>lz' % abbr,
                'data/banim/banim_%s_modes.bin' % abbr])
    with open(BANIM_LINKER, 'a', encoding='utf-8') as f:
        f.write('\n# Manchego Stars imported battle anim (#90): %s\n' % uid)
        f.write('\n'.join(block) + '\n')

    with open(BANIM_DATA_C, encoding='utf-8') as f:
        text = f.read()
    text, anim_id = banim_append_row(text, abbr)
    with open(BANIM_DATA_C, 'w', encoding='utf-8') as f:
        f.write(text)
    with open(BANIM_POINTER_H, 'a', encoding='utf-8') as f:
        f.write('// battle animation 0x%X (Manchego Stars #90: %s)\n' % (anim_id, uid))
        for sym, ty in [('modes_bin', 'int'), ('motion_o', 'char'),
                        ('oam_r_bin', 'char'), ('oam_l_bin', 'char'), ('agbpal', 'char')]:
            f.write('extern %s banim_%s_%s;\n' % (ty, abbr, sym))
    return anim_id


def inject_enemy_class_battle_anims(campaign, verbose=True):
    """Import + class-bind a battle animation for every enemy_class_reskins entry carrying a
    `battle_anim:` block (#90). MUST run after inject_enemy_class_reskins (the reskin clone
    class it repoints must already exist).

    campaign.yaml (on a reskin entry):
        battle_anim:
          source: wildling               # dir under engine/battle_anims/_vendored/
          weapons:                        # one per weapon-mode the donor AnimConf keys
            - {dir: axe,     txt: Axe.txt,     abbr: kgru_ax, wtypes: ["0x0100 | ITYPE_AXE"]}
            - {dir: handaxe, txt: Handaxe.txt, abbr: kgru_ha,
               wtypes: ["ITEM_AXE_HANDAXE", "ITEM_AXE_TOMAHAWK", "ITEM_AXE_HATCHET"]}
            - {dir: unarmed, txt: Unarmed.txt, abbr: kgru_un, wtypes: ["0x0100 | ITYPE_ITEM"]}
    Each `wtypes` literal must match an entry in the donor class's AnimConf verbatim (they are
    repointed by literal). A class's weapons share ONE palette (same creature, one colour set).

    !! OFF-BY-ONE (as in inject_battle_anims): the AnimConf `.index` is animId + 1
       (GetBattleAnimationId returns idx - 1). Encode anim_id + 1."""
    reskins = [r for r in enemy_class_reskins(campaign) if r.get('battle_anim')]
    if not reskins:
        if verbose:
            print('  (no class battle_anim blocks declared)')
        return
    os.makedirs(BANIM_DATA_DIR, exist_ok=True)
    os.makedirs(BANIM_GFX_DIR, exist_ok=True)
    vendored = os.path.join(REPO, 'engine', 'battle_anims', '_vendored')

    for rk in reskins:
        ba = rk['battle_anim']
        src_dir = os.path.join(vendored, ba['source'])
        weapons = ba['weapons']
        # Optional enemy-faction palette pass: a community anim ships its NATIVE (often
        # ally-blue) palette, but a reskin is always hostile, so recolour to the enemy ramp
        # (the engine reads agbpal bank BANIMPAL_RED for enemies). `recolor:` names a
        # feditor_to_banim recolour fn; absent -> the anim keeps its native colours.
        recolor = BANIM_RECOLORS[ba['recolor']] if ba.get('recolor') else None

        # Import each weapon-mode anim -> a new animId; collect (wtype, animId) repoints. Each
        # anim carries its OWN agbpal (the engine loads a battle sprite's palette per-animation),
        # so weapons keep their native <=15-colour set -- the same creature's body reads
        # consistently across them without forcing all weapons into one shared 16-colour bank.
        repoints = []
        for w in weapons:
            wdir = os.path.join(src_dir, w['dir'])
            res = feditor_to_banim.build_import(w['abbr'], os.path.join(wdir, w['txt']), wdir,
                                                recolor=recolor)
            anim_id = _write_imported_banim_assets(w['abbr'], res, rk['id'])
            for wt in w['wtypes']:
                repoints.append((wt, anim_id))
            if verbose:
                print('  %-16s = import %s (animId 0x%X, %d frame(s))'
                      % (rk['id'], w['abbr'], anim_id, len(res['sheets'])))

        # A private class-level AnimConf = clone of the donor's, each weapon entry repointed.
        base_conf = _class_field_symbol(rk['base'], 'pBattleAnimDef')
        new_conf = 'AnimConf_%s' % rk['id'].replace('-', '_')
        with open(BANIMCONF_C, encoding='utf-8') as f:
            conf = f.read()
        first_wt, first_id = repoints[0]
        conf = banim_clone_conf(conf, base_conf, new_conf, first_wt, first_id + 1)
        for wt, aid in repoints[1:]:
            conf = banim_repoint_conf(conf, new_conf, wt, aid + 1)
        with open(BANIMCONF_C, 'w', encoding='utf-8') as f:
            f.write(conf)
        with open(BANIM_EKRBATTLE_H, 'a', encoding='utf-8') as f:
            f.write('extern CONST_DATA struct BattleAnimDef %s[]; /* Manchego Stars #90 */\n'
                    % new_conf)

        # Point the reskin clone class's .pBattleAnimDef at the new class-level AnimConf.
        with open(CLASSES_C, encoding='utf-8') as f:
            ctext = f.read()
        ctext = set_class_field_symbol(ctext, rk['slot'], 'pBattleAnimDef', new_conf)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(ctext)
        if verbose:
            print('  %-16s = %s bound on %s' % (rk['id'], new_conf, rk['slot']))


# --- Map tileset + layout (#40/#41) ----------------------------------------------
# A GBAFE map = 4 data pieces the decomp wires through gChapterDataAssetTable
# (data/data_8B363C.s) and incbins in data/const_data_chapter_maps.s: tile GRAPHICS
# (.4bpp.lz), PALETTE (.gbapal), tile CONFIG (.bin.lz = 8192B TSA + 1024B terrain),
# and a per-map LAYOUT (.bin.lz). A chapter's struct (chapter_settings.json -> jsonproc
# -> chapter_settings.h) holds u8 *indices* into the asset table for each piece.
#
# The Snowy Bern community tileset (FEU t/7204; see CREDITS.md) ships these pieces in
# FEBuilder's format, which is byte-identical to the decomp's, so registering it is a
# straight drop-in -- no grit/Map Hacking Suite recompile. We append its gfx/palette/
# config plus a test LAYOUT to the asset table and repoint the TEST chapter at them, so
# `make` + New Game load-tests the tileset in-engine (the same hijack inject_test_chapter
# uses). Authoring real Tiled layouts (.tmx -> .bin) is the next step (#40 task 2 / #20).

MAP_GFX_DIR = os.path.join(DECOMP, 'graphics', 'map')
MAP_LAYOUT_DIR = os.path.join(MAP_GFX_DIR, 'layout')
CONST_MAPS_S = os.path.join(DECOMP, 'data', 'const_data_chapter_maps.s')
ASSET_TABLE_S = os.path.join(DECOMP, 'data', 'data_8B363C.s')
CHAPTER_SETTINGS_JSON = os.path.join(DECOMP, 'src', 'data', 'chapter_settings.json')

# The campaign's tilesets (maps/tilesets/<name>/, vendored via map_tileset_tool
# import). Each registers under ObjectType<Stem>/MapPalette<Stem>/
# TileConfiguration<Stem> asset labels (_register_tileset). Further tilesets
# (e.g. cave-interior, #40/#23) register in the chapter injector that first
# consumes them.
WINTER_TILESET = 'snowy-bern'         # shared winter overworld (#41), stem Snow
WINTER_TEST_LAYOUT = ('ChTestSnowMap', 'ch-test-snowfield')  # (asset label, campaign source stem)


def _append_asm_table_words(path, table_label, words):
    """Append `.word <w>` lines after the last consecutive `.word` of an asm array
    (`table_label:`). Returns the 0-based index the first appended word lands at."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith(table_label + ':')), None)
    if start is None:
        sys.exit('ERROR: table %r not found in %s' % (table_label, path))
    last, count = None, 0
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith('.word'):
            last, count = i, count + 1
        elif s and not s.startswith('@'):
            break
    if last is None:
        sys.exit('ERROR: no .word entries under %r' % table_label)
    lines[last + 1:last + 1] = ['\t.word %s\n' % w for w in words]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))
    return count  # next free index == prior entry count


def _asm_table_word_index(path, table_label, word_label):
    """0-based index of `.word <word_label>` within the asm array `table_label:`. Used
    to look up an asset registered by an earlier injector (e.g. the winter tileset)."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith(table_label + ':')), None)
    if start is None:
        sys.exit('ERROR: table %r not found in %s' % (table_label, path))
    idx = 0
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith('.word'):
            if s.split(None, 1)[1].strip() == word_label:
                return idx
            idx += 1
        elif s and not s.startswith('@'):
            break
    sys.exit('ERROR: .word %r not found under %r in %s' % (word_label, table_label, path))


    # A tileset .gbapal is TWO sets of five banks, not ten independent ones. DisplayBmTile
# (bmmap.c) draws a VISIBLE tile from BG palette bank 6 and a FOGGED tile from bank 11,
# and UnpackChapterMapPalette loads our ten banks at BG 6..15 -- so banks 0-4 are the lit
# set and banks 5-9 are its fog copy. A vendored community tileset routinely recolours only
# the lit half, because most maps never turn fog on: Snowy Bern's lit half is winter and its
# fog half is still vanilla Bern, which is why ch04's fogged tiles showed the grass we
# winterized away (Nicolas, 2026-07-31). Derive the fog half from OUR lit half rather than
# trusting the vendor's.
#
# `haze` is the lerp-toward-white factor. Vanilla authors each tileset's fog half by hand and
# the direction depends on the setting -- its outdoor palette hazes WHITE (MapPalette1: median
# k = 0.5 measured across all five bank pairs) while interior palettes darken instead. Snow
# under fog is the outdoor case.
TILESET_FOG_HAZE = {'snowy-bern': 0.5}
FOG_BANK_OFFSET = 5             # banks 0-4 lit -> banks 5-9 fog


def derive_fog_banks(palette, haze):
    """Return `palette` (a 320 B .gbapal) with its fog half rebuilt from its lit half.

    Pure, so it is unit-testable without a build. Each lit colour is lerped toward white in
    BGR555 space; index 0 is the transparent/backdrop entry and is carried across untouched
    so the fog copy keeps the same key colour."""
    out = bytearray(palette)
    for bank in range(FOG_BANK_OFFSET):
        for i in range(16):
            lit = struct.unpack_from('<H', palette, bank * 32 + i * 2)[0]
            if i == 0:
                fog = lit
            else:
                ch = [(lit >> s) & 31 for s in (0, 5, 10)]
                ch = [min(31, int(round(c + (31 - c) * haze))) for c in ch]
                fog = ch[0] | (ch[1] << 5) | (ch[2] << 10)
            struct.pack_into('<H', out, (bank + FOG_BANK_OFFSET) * 32 + i * 2, fog)
    return bytes(out)


def _register_tileset(campaign, tileset, label_stem, comment):
    """Copy a vendored tileset's 3 pieces (maps/tilesets/<tileset>/, the
    map_tileset_tool import format) into the decomp, register their incbins in
    CONST_MAPS_S under `comment` + fresh gChapterDataAssetTable slots, and return
    {'obj','pal','cfg'} asset indices. Labels are ObjectType<Stem> /
    MapPalette<Stem> / TileConfiguration<Stem>; gfx + config ride the Makefile
    %.lz rule, the palette stays raw like vanilla MapPaletteN.gbapal."""
    ts_dir = os.path.join(REPO, 'campaigns', campaign, 'maps', 'tilesets', tileset)
    assets = [  # (asset-table label, source ext, incbin ext)
        ('ObjectType%s' % label_stem, '4bpp', '4bpp.lz'),
        ('MapPalette%s' % label_stem, 'gbapal', 'gbapal'),
        ('TileConfiguration%s' % label_stem, 'bin', 'bin.lz'),
    ]
    incbin = ['\n/* %s */' % comment]
    haze = TILESET_FOG_HAZE.get(tileset)
    for label, src_ext, inc_ext in assets:
        src = os.path.join(ts_dir, '%s.%s' % (tileset, src_ext))
        dst = os.path.join(MAP_GFX_DIR, '%s.%s' % (label, src_ext))
        if src_ext == 'gbapal' and haze is not None:
            # Rebuild the fog half from our winterized lit half (see TILESET_FOG_HAZE).
            # Derived at build time, so the vendored .gbapal stays the one source of truth
            # and a future repaint of the lit banks carries into fog for free. Only the COPY
            # changes -- the incbin/label registration below still has to happen, or the
            # asset table references a symbol nothing defines.
            with open(src, 'rb') as f:
                pal = f.read()
            with open(dst, 'wb') as f:
                f.write(derive_fog_banks(pal, haze))
        else:
            shutil.copyfile(src, dst)
        incbin += ['\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
                   '\t.incbin "graphics/map/%s.%s"' % (label, inc_ext)]
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join(incbin) + '\n')
    base = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                   [a[0] for a in assets])
    return {'obj': base, 'pal': base + 1, 'cfg': base + 2}


def inject_winter_tileset(campaign, verbose=True):
    """Register the winter tileset (#41) + a flat test layout and repoint the test
    chapter at them, so a build load-tests the tileset in-engine (#40)."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')

    # 1. Tileset pieces -> decomp + asset table (shared path, #40).
    ts_idx = _register_tileset(campaign, WINTER_TILESET, 'Snow',
                               'Manchego Stars winter tileset (#40/#41)')

    # 2. Copy the test layout source (.mar + .json -> Makefile mar_to_map -> .bin -> .lz),
    #    register its incbin + asset-table slot.
    layout_label, stem = WINTER_TEST_LAYOUT
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (layout_label, ext)))
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars winter test layout (#40/#41) */',
            '\t.align 2, 0', '\t.global %s' % layout_label, '%s:' % layout_label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % layout_label]) + '\n')
    layout_idx = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                         [layout_label])

    # 3. Repoint the TEST chapter (the inject_test_chapter target) at the winter tileset
    #    + flat layout. obj2/anim/changes off -> the flat field needs none.
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    cmap = settings['chapters'][TEST_CHAPTER_INDEX]['map']
    cmap.update({'obj1Id': ts_idx['obj'], 'obj2Id': 0,
                 'paletteId': ts_idx['pal'], 'tileConfigId': ts_idx['cfg'],
                 'mainLayerId': layout_idx, 'objAnimId': 0, 'paletteAnimId': 0,
                 'changeLayerId': 0})
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    if verbose:
        print('  %s tileset -> asset table [%d..%d]; test chapter (idx %d) repointed'
              % (WINTER_TILESET, ts_idx['obj'], layout_idx, TEST_CHAPTER_INDEX))


def inject_title_screen(campaign, verbose=True):
    """Replace the boot title screen's gold "FIRE EMBLEM" logo with "MANCHEGO
    STARS" in the same gold letterform style (gen_gold_title hand-built glyphs +
    the logo's own gradient/outline/shadow). Only the image source changes: the
    decomp's generic gbagfx rule rebuilds title_fire_emblem_logo.4bpp(.lz) from
    the .png, the palette is preserved, and gSprite_Title_FireEmblemLogo /
    data_titlescreen.s are untouched. Idempotent (rebuilds a fresh canvas)."""
    import gen_gold_title
    ts_dir = os.path.join(DECOMP, 'graphics', 'titlescreen')

    # 1. Logo graphic (256x64): "MANCHEGO STARS" gold in the top 32 rows; the two-line
    #    subtitle in the bottom 32 rows (the half the second sprite draws). title_logos
    #    is read as tiles (pixel edits don't map to sprite regions), but the logo graphic
    #    maps cleanly, so both texts live here.
    logo_png = os.path.join(ts_dir, 'title_fire_emblem_logo.png')
    gen_gold_title.compose_logo('MANCHEGO STARS',
                                ('RIME OF THE', 'FROSTMAIDEN')).save(logo_png)
    for stale in ('.4bpp', '.4bpp.lz'):
        p = logo_png[:-4] + stale
        if os.path.exists(p):
            os.remove(p)

    # 2. titlescreen.c: the vanilla second logo sprite (0x2080) draws the bottom 32 rows
    #    as a blended glow at Y=53 (oam0=1077), overlapping the logo. Repoint it to a
    #    plain draw at Y=80 so those rows (our subtitle) render BELOW the logo; and drop
    #    the "THE SACRED STONES" scroll banner. Idempotent.
    ts_c = os.path.join(DECOMP, 'src', 'titlescreen.c')
    with open(ts_c, encoding='utf-8') as f:
        src = f.read()
    src = src.replace(
        '    PutSpriteExt(2, 4, 1077, gSprite_Title_FireEmblemLogo, 0x2080);',
        '    PutSpriteExt(1, 4, 80, gSprite_Title_FireEmblemLogo, 0x2080); '
        '/* manchego: subtitle row, below the logo */')
    src = src.replace(
        '    PutSpriteExt(1, 16, 85, gSprite_Title_SacredStonesBanner, 0x31A0);',
        '    /* manchego: scroll banner dropped (subtitle is in the logo graphic) */')
    # Disable the title's idle timeout: after ~13.5s with no input Title_IDLE fires
    # GAME_ACTION_CLASS_REEL -> the attract/class-reel demo, which crashes (we removed the
    # op-anim path + the demo's class/chapter data no longer matches). Never time out --
    # the title just holds with its music until the player presses START.
    src = src.replace(
        '        if (proc->timer_idle == 815)',
        '        if (0) /* manchego: never time out to the attract demo (it crashes) */')
    with open(ts_c, 'w', encoding='utf-8') as f:
        f.write(src)

    # 3. Theme the backdrop: recolor the mountain/sky bg palette to icy blue and blank
    #    the two-dragon foreground (off-theme). Recolour SETS hue (idempotent -- rebuilds
    #    don't drift); blanking the dragon tiles makes BG0 fully transparent. We edit the
    #    COMMITTED JASC .pal source (the .gbapal is build-generated -- %.gbapal: %.pal --
    #    so it isn't present at inject time on a clean checkout) and drop the stale .gbapal
    #    so gbagfx regenerates it blue. Index 0 (the magenta placeholder) is left alone.
    import colorsys
    pal_path = os.path.join(ts_dir, 'title_main_background.pal')
    with open(pal_path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i in range(4, len(lines)):           # lines 0-2 = header, line 3 = index 0
        parts = lines[i].split()
        if len(parts) != 3:
            continue
        r, g, b = (int(c) / 255 for c in parts)
        _, l, s = colorsys.rgb_to_hls(r, g, b)
        nr, ng, nb = colorsys.hls_to_rgb(0.57, l, max(s, 0.45))  # ~205deg icy blue
        lines[i] = '%d %d %d' % (round(nr * 255), round(ng * 255), round(nb * 255))
    with open(pal_path, 'w', encoding='utf-8', newline='') as f:
        f.write('\r\n'.join(lines) + '\r\n')   # gbagfx requires CRLF .pal line endings
    gbapal = pal_path[:-4] + '.gbapal'
    if os.path.exists(gbapal):
        os.remove(gbapal)

    dragon_png = os.path.join(ts_dir, 'title_dragon_foreground.png')
    from PIL import Image as _Image
    dr = _Image.open(dragon_png)
    blank = _Image.new('P', dr.size, 0)
    blank.putpalette(dr.getpalette())
    blank.save(dragon_png)
    for stale in ('.4bpp', '.4bpp.lz'):
        p = dragon_png[:-4] + stale
        if os.path.exists(p):
            os.remove(p)
    if verbose:
        print('  boot title -> "MANCHEGO STARS" + "RIME OF THE / FROSTMAIDEN"; '
              'bg recolored icy blue, dragons removed')


def inject_title_theme(campaign, verbose=True):
    """Recolor the chapter-title banner palettes from campaign.yaml `title_theme`.

    The banner's look is PALETTE data, not image data: chapter_title.c
    sub_80895B4 applies gPal_08A07AD8 / gPal_08A07C58 (data/data_A01CC4.s,
    incbin'd straight from baserom). gPal_08A07C58 is six tint pairs
    (normal+dim) of 16 colors; the GREEN pair (sub-pals 0+1) is what the
    Status screen draws the title card with (config 0x80) -- letters ride
    indices 1-6 and the banner plaque's leaf ramp indices 8-15. The in-map
    chapter intro uses the gray pair (config 8 -> +0xA0), left untouched.
    gPal_08A07AD8 (9 colors) is the bonus-claim screen's green ramp.

    We replace the six vanilla letter greens 1:1 with the YAML colors and
    hue-map every other green-dominant color (plaque leaves, dim variant)
    into the same family, then repoint the .s incbins at generated .bin
    files (data_A01CC4.s is in PATCHED_DECOMP_FILES, so each build starts
    from the vanilla incbins).
    """
    import colorsys
    import struct

    cfg_path = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg_path, encoding='utf-8') as f:
        theme = (yaml.safe_load(f) or {}).get('title_theme')
    if not theme:
        return
    letters = [tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
               for h in theme['letter_colors']]
    if len(letters) != 6:
        sys.exit('ERROR: title_theme.letter_colors must list 6 colors (light->dark)')
    vanilla_letters = [(240, 248, 248), (200, 232, 200), (160, 200, 160),
                       (112, 152, 112), (64, 112, 64), (16, 56, 16)]
    exact = dict(zip(vanilla_letters, letters))
    # family hue/extra saturation from the mid letter color
    target_h, _, target_s = colorsys.rgb_to_hls(*[v / 255 for v in letters[2]])

    def recolor(rgb):
        if rgb in exact:
            return exact[rgb]
        h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in rgb])
        if not (0.19 <= h <= 0.47 and s > 0.08):  # not green family
            return rgb
        r, g, b = colorsys.hls_to_rgb(target_h, l, max(s, min(target_s, 0.6)))
        return tuple(round(v * 255) for v in (r, g, b))

    def gba(rgb):
        r, g, b = rgb
        return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

    with open(os.path.join(DECOMP, 'baserom.gba'), 'rb') as f:
        rom = f.read()

    def transform(offset, count, recolor_through):
        out = []
        for i in range(count):
            v = struct.unpack_from('<H', rom, offset + i * 2)[0]
            rgb = ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)
            out.append(gba(recolor(rgb) if i < recolor_through else rgb))
        return struct.pack('<%dH' % count, *out)

    pals = [  # (asm file, label, baserom offset, color count, recolor first N)
        # title letter palettes (chapter_title.c sub_80895B4)
        ('data/data_A01CC4.s', 'gPal_08A07AD8', 0xA07AD8, 9, 9),
        # sub_80895B4's config&1 table actually continues past the 9-color
        # label: the save-slot select (SaveMenuInitSlotPalette) reads pair 0's
        # normal row tail + the +0x10 dim row straight through these two
        # follower incbins -- without them the unselected slot banners stay
        # vanilla green (Nicolas, 2026-06-10 tour review). B0A's first 7 are
        # also the hard-save blink ramp; the rest is the per-difficulty pairs,
        # left vanilla.
        ('data/data_A01CC4.s', 'gUnknown_08A07AEA', 0xA07AEA, 0x10, 0x10),
        ('data/data_A01CC4.s', 'gUnknown_08A07B0A', 0xA07B0A, 0x70, 7),
        ('data/data_A01CC4.s', 'gPal_08A07C58', 0xA07C58, 0xC0, 32),
        # Status-screen banner PLAQUE sprites (uichapterstatus.c, OBJ rows 8-9;
        # pal 0 = the leaf-green ramp, pal 1 = blue-gray and passes through)
        ('data/data_A21658.s', 'Pal_PlayStatusSprites', 0xA2E1B8, 0x20, 0x20),
    ]
    for asm_rel, label, offset, count, n in pals:
        bin_rel = 'data/campaign_%s.bin' % label.lower()
        with open(os.path.join(DECOMP, bin_rel), 'wb') as f:
            f.write(transform(offset, count, n))
        asm_path = os.path.join(DECOMP, asm_rel)
        with open(asm_path, encoding='utf-8') as f:
            asm = f.read()
        old = '%s:  @ 0x0%X\n\t.incbin "baserom.gba", 0x%X, 0x%X' \
              % (label, 0x8000000 + offset, offset, count * 2)
        new = '%s:  @ 0x0%X (recolored: campaign title_theme)\n\t.incbin "%s"' \
              % (label, 0x8000000 + offset, bin_rel)
        if old not in asm:
            sys.exit('ERROR: incbin for %s not found in %s' % (label, asm_path))
        with open(asm_path, 'w', encoding='utf-8') as f:
            f.write(asm.replace(old, new))
    if verbose:
        print('  title banner palettes -> %s family (letters 1:1, greens hue-mapped)'
              % theme['letter_colors'][2])


# --- Prologue chapter wire-up (#20) -----------------------------------------------
# Stand up the designed ch00 ("A Dagger of Ice") as the New Game target: register its
# winter layout onto chapter 0, rewrite the prologue rosters to Scramsax+Hlin vs
# Sephek+guards, strip the vanilla Eirika/Seth/Valter cutscene down to a deploy +
# DefeatBoss, name the three guests, and flag Hlin's death as game over. Runs AFTER
# inject_winter_tileset (reuses its registered snow tileset assets). Replaces
# inject_test_chapter as main()'s in-engine entry. Structural unit data (class/level/
# position/items/ai) tracks campaigns/.../chapters/ch00-prologue-a-dagger-of-ice.yaml;
# names are read from that YAML so they live in one place.

def _load_prologue_chapter(campaign):
    path = os.path.join(REPO, 'campaigns', campaign, 'chapters', PROLOGUE_CHAPTER_YAML)
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def inject_prologue(campaign, verbose=True, montage=False):
    """Wire the designed Prologue (#20) onto chapter 0 as the New Game target."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    # Cold-open guests ride non-PORTRAIT_MAP vanilla slots (PROLOGUE_*_SLOT). Classes mirror
    # the ch00 YAML: a strong promoted "Jeigan" (Scramsax/Hero) + the frail must-survive lead
    # (Hlin/Fighter, UNPROMOTED -- the frailty is the point) -- the vanilla Prologue
    # Seth+Eirika dynamic. (Difficulty lives in the
    # roster levels/items below + the guest stat patch in step 4b.)
    hlin_slot, scram_slot, sephek_slot = (
        PROLOGUE_HLIN_SLOT, PROLOGUE_SCRAMSAX_SLOT, PROLOGUE_SEPHEK_SLOT)
    # Structural data the build emits comes from the ch00 YAML (single source of truth).
    chap = _load_prologue_chapter(campaign)
    by_id = {u['id']: u for u in chap['player_units'] + chap['enemy_units']}
    sephek_item = fe_item_enum(by_id['sephek-kaltro']['inventory'][0])   # ice-longsword -> steel
    # Hlin = frail must-survive lead -> UNPROMOTED Fighter (frail like vanilla Eirika next to a
    # promoted unit; a custom FEMALE Fighter map sprite distinguishes her from the male Fighter
    # guards -- see inject_map_sprites). Scramsax = dominant promoted "Jeigan" (Hero, the Seth
    # analog) -> a real Steel Sword so he can carry the map. (cf. ch00 YAML inventories.)
    hlin_class, scram_class = 'CLASS_FIGHTER', 'CLASS_HERO'
    hlin_items = 'ITEM_AXE_HANDAXE, ITEM_VULNERARY'
    scram_items = 'ITEM_SWORD_STEEL, ITEM_AXE_HANDAXE'

    # 1. Register the prologue layout (.mar + .json -> Makefile mar_to_map -> .bin -> .lz) and
    #    point the HOST chapter (Ch1) at it + the winter tileset. We host the prologue in the
    #    Ch1 chapter + event group, NOT the vanilla prologue slot (0): the prologue slot's
    #    event group (asset[7]) garbles the gameplay HUD/terrain display when loaded with our
    #    stripped chapter (garbage band, bad string-pointer loads), while a normal chapter's
    #    group (Ch1Events, asset[10]) loads cleanly -- proven by inject_test_chapter. New Game
    #    redirects 0 -> 1 (step 6). The prologue slot is left vanilla and never loaded.
    obj_idx, pal_idx, cfg_idx, layout_idx = _register_chapter_map(
        maps_dir, PROLOGUE_LAYOUT, 'Manchego Stars prologue layout (#20)')
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    host = settings['chapters'][PROLOGUE_HOST_INDEX]
    host['map'].update({'obj1Id': obj_idx, 'obj2Id': 0, 'paletteId': pal_idx,
                        'tileConfigId': cfg_idx, 'mainLayerId': layout_idx,
                        'objAnimId': 0, 'paletteAnimId': 0, 'changeLayerId': 0})
    # The goal banner/objective display is chapter data, not events -- the host (vanilla
    # Ch1) says "Seize gate". Copy the vanilla Prologue's defeat_boss goal block.
    host['goal'] = settings['chapters'][PROLOGUE_CHAPTER_INDEX]['goal']
    # The New Game save-slot select draws the VANILLA prologue slot's title-card
    # IMAGE ("Prologue: The Fall of Renais") -- it reads chapter 0's chapTitleId,
    # not the host's. Point slot 0 at the host's card (recomposed in step 4a);
    # slot 0 is never loaded as a chapter, so only this menu metadata matters.
    settings['chapters'][PROLOGUE_CHAPTER_INDEX]['chapTitleId'] = host['chapTitleId']
    # fadeToBlack=1: the intro ends on black, not a map fade-in (see _retarget_host_chapter) --
    # our opening is a BG cutscene (the BeginningScene BACGs), so the vanilla map fade-in would
    # FLASH the map first. Slot 1 shipped with fadeToBlack=0; set it so the prologue matches.
    host['fadeToBlack'] = 1
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    # 2. Rewrite the two prologue rosters. redaCount=0 places units statically at
    #    xPosition/yPosition (like inject_test_chapter); the boss rides the ONEILL slot
    #    (CA_BOSS marks it a boss for autolevel/UI -- the DefeatBoss EVENT flag comes from
    #    the flagged defeat quote in step 5, not from CA_BOSS). Positions/levels/items from
    #    the chapter YAML (0-indexed x,y). AI: boss = Breguet's stationary-aggressive bytes
    #    {AI_A_03 ActionStanding, AI_B_03 NeverMove, config} (cp_data.c gAi1/2ScriptTable) --
    #    NOT O'Neill's {0x6,0x3} "DoNothing", which only works because the vanilla tutorial
    #    event-scripts his attack. Guards attack in range (AI_A_00).
    ally = (
        '{\n'
        '    {\n'
        '        .charIndex = CHARACTER_%s, /* Hlin -- frail must-survive lead */\n'
        '        .classIndex = %s,\n'
        '        .leaderCharIndex = CHARACTER_%s,\n'
        '        .allegiance = FACTION_ID_BLUE,\n'
        '        .level = 3,\n'
        '        .xPosition = 8,\n'
        '        .yPosition = 5,\n'
        '        .redaCount = 0,\n'
        '        .items = { %s },\n'
        '    },\n'
        '    {\n'
        '        .charIndex = CHARACTER_%s, /* Scramsax -- strong veteran (our Jeigan) */\n'
        '        .classIndex = %s,\n'
        '        .leaderCharIndex = CHARACTER_%s,\n'
        '        .allegiance = FACTION_ID_BLUE,\n'
        '        .level = 1,\n'
        '        .xPosition = 13,\n'
        '        .yPosition = 9,\n'
        '        .redaCount = 0,\n'
        '        .items = { %s },\n'
        '    },\n'
        '    { 0 },\n'
        '}' % (hlin_slot, hlin_class, hlin_slot, hlin_items,
               scram_slot, scram_class, hlin_slot, scram_items))
    enemy = (
        '{\n'
        '    {\n'
        '        .charIndex = CHARACTER_%s, /* Sephek -- boss; escapes in the ending */\n'
        '        .classIndex = CLASS_MYRMIDON,\n'
        '        .allegiance = FACTION_ID_RED,\n'
        '        .level = 5,\n'
        '        .xPosition = 14,\n'
        '        .yPosition = 8,\n'
        '        .redaCount = 0,\n'
        '        .items = { %s },\n'
        '        .ai = {0x3, 0x3, 0x9, 0x20}, /* attack in place, never move (Breguet) */\n'
        '    },\n'
        '    {\n'
        '        .charIndex = 0x80, /* Torg\'s caravan guard */\n'
        '        .classIndex = CLASS_FIGHTER,\n'
        '        .allegiance = FACTION_ID_RED,\n'
        '        .level = 2,\n'
        '        .xPosition = 14,\n'
        '        .yPosition = 7,\n'
        '        .redaCount = 0,\n'
        '        .items = { ITEM_AXE_IRON },\n'
        '        .ai = {0x0, 0xa, 0x0, 0x0},\n'
        '    },\n'
        '    {\n'
        '        .charIndex = 0x82, /* Torg\'s caravan guard */\n'
        '        .classIndex = CLASS_FIGHTER,\n'
        '        .allegiance = FACTION_ID_RED,\n'
        '        .level = 2,\n'
        '        .xPosition = 13,\n'
        '        .yPosition = 7,\n'
        '        .redaCount = 0,\n'
        '        .items = { ITEM_AXE_IRON },\n'
        '        .ai = {0x0, 0xa, 0x0, 0x0},\n'
        '    },\n'
        '    { 0 },\n'
        '}' % (sephek_slot, sephek_item))
    with open(CH1_UDEFS_H, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(udefs, 'UnitDef_Event_Ch1Ally[] =', ally, CH1_UDEFS_H)
    udefs = _replace_brace_block(udefs, 'UnitDef_Event_Ch1Enemy[] =', enemy, CH1_UDEFS_H)
    with open(CH1_UDEFS_H, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Strip the Ch1 cutscene scripting (like inject_test_chapter, which renders cleanly):
    #    empty the Turn/Character/Location lists and null the tutorial list, then replace the
    #    beginning scene with a bare deploy of both rosters. The Misc list keeps the win/lose
    #    machinery in the vanilla Prologue's shape (prologue-eventinfo.h): DefeatBoss = AFEV
    #    on EVFLAG_DEFEAT_BOSS, which Sephek's FLAGGED DEFEAT QUOTE sets on his death
    #    (step 5; CA_BOSS alone sets nothing) -> runs the ending scene; CauseGameOverIfLordDies = AFEV on
    #    EVFLAG_GAMEOVER, which Hlin's flagged defeat quote sets (step 5).
    with open(CH1_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    for name in ('EventListScr_Ch1_Turn', 'EventListScr_Ch1_Character',
                 'EventListScr_Ch1_Location'):
        info = _replace_brace_block(info, name + '[] =', '{\n    END_MAIN\n}', CH1_EVENTINFO_H)
    misc = ('{\n    DefeatBoss(EventScr_Ch1_EndingScene)\n'
            '    CauseGameOverIfLordDies\n'
            '    END_MAIN\n}')
    info = _replace_brace_block(info, 'EventListScr_Ch1_Misc[] =', misc, CH1_EVENTINFO_H)
    info = _replace_brace_block(info, 'EventListScr_Ch1_Tutorial[] =',
                                '{\n    NULL\n}', CH1_EVENTINFO_H)
    with open(CH1_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    with open(CH1_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    # The chapter-start auto-cursor (ProcFun_ResetCursorPosition) now centers the camera +
    # cursor on the first player unit even when the lord rides a non-LORD slot (engine fix in
    # _patch_player_start_cursor_guard). Begin scene = the ch00 YAML's locked chapter_start
    # script, staged vanilla-Prologue-style: deploy the allies, brown-box location card
    # ("The Eastway", msg 0x664 -- step 4c), the opening dialogue ON the map (msg 0x90D;
    # vanilla 0x910's convention -- FE8 ships no snow background, and a green BG_PLAIN_*
    # reads wrong in a two-year winter, so the snowy map IS the backdrop), THEN deploy the
    # enemies -- Sephek "steps out" exactly when his interrupt lands in the text -- and
    # flash him to mark the boss before handing over control.
    begin = ('{\n    LOAD1(1, UnitDef_Event_Ch1Ally)\n    ENUN\n'
             '    BROWNBOXTEXT(0x664, 8, 8)\n'
             '    STAL(30)\n'
             '    FlashCursor(CHARACTER_%s, 60)\n'
             '    MUSI\n'
             '    Text(0x90D)\n'
             '    LOAD1(1, UnitDef_Event_Ch1Enemy)\n    ENUN\n'
             '    FlashCursor(CHARACTER_%s, 60)\n'
             '    Text(0x90E)\n'
             '    MUNO\n'
             '    NoFade\n    ENDA\n}' % (hlin_slot, sephek_slot))
    script = _replace_brace_block(
        script, 'EventScr_Ch1_BeginningScene[] =', begin, CH1_EVENTSCRIPT_H)
    # DefeatBoss ending = the YAML's locked chapter_end script (msg 0x918), vanilla
    # Prologue EndingScene shape minus its worldmap/supply ENUT flags: victory sting,
    # dialogue ON the map (over the spot where Sephek vanished -- same no-snow-BG
    # rationale as the opening), fade to black (the locked script ends on
    # fade_to_black -- no location-card tease, decided 2026-06-10), then advance.
    ending = ('{\n    MUSC(SONG_VICTORY)\n'
              '    Text(0x918)\n    FADI(16)\n'
              '    MNC2(0x2)\n    ENDA\n}')
    script = _replace_brace_block(
        script, 'EventScr_Ch1_EndingScene[] =', ending, CH1_EVENTSCRIPT_H)
    with open(CH1_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 4. Names (read from the chapter YAML so they live in one place; fe_name handles
    #    FE8's 12-char buffer -- see [[manchego-stars-fe-name-truncation]]). chap/by_id
    #    were loaded at the top of the function.
    name_slots = [(PROLOGUE_HLIN_SLOT, 'hlin-trollbane'),
                  (PROLOGUE_SCRAMSAX_SLOT, 'scramsax'),
                  (PROLOGUE_SEPHEK_SLOT, 'sephek-kaltro')]
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for slot, uid in name_slots:
        unit = by_id[uid]
        unit.setdefault('id', uid)
        set_message_body(lines, vanilla_name_text_id(slot),
                         name_message_body(display_name(unit)))
    # 4a. Chapter title, both places FE8 keeps it: the intro/status banner is a 4bpp
    #     IMAGE (chap_title_data[chapTitleId], not text) -- recompose it from vanilla
    #     glyphs in the YAML's title (gen_chapter_title) and overwrite the host slot's
    #     card; the save-select/status TEXT rides chapTitleTextId. Stale .4bpp/.lz
    #     intermediates are removed so make re-converts the new PNG.
    set_message_body(lines, host['chapTitleTextId'],
                     name_message_body(chap['title']))
    # The New Game save-slot select shows the VANILLA prologue slot's title text
    # ("Prologue: <title>" with the prefix screen-composed) -- it reads chapter 0,
    # not the host, so retitle that slot's text too.
    set_message_body(lines,
                     settings['chapters'][PROLOGUE_CHAPTER_INDEX]['chapTitleTextId'],
                     name_message_body(chap['title']))
    # The copied goal block still points its Status-screen objective at vanilla's
    # "Defeat O'Neill" -- rewrite it as "Defeat <boss fe_name>" (vanilla keeps this
    # short; the YAML's full objective.description is for docs/banners).
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + display_name(by_id['sephek-kaltro'])))
    # Was an inline copy of _write_chapter_title_card, carrying the same delete-and-hope bug
    # (#245): make does not re-derive a deleted .4bpp.lz, so the prologue's card either broke
    # the build or silently never landed. One helper now, which owns the conversion.
    _write_chapter_title_card(host, 'Prologue: ' + chap['title'])

    # 4c. Dialogue (ch00 dialogue pass, 2026-06-10): message bodies are GENERATED from
    #     the chapter YAML's locked `script:` blocks + quote fields -- the YAML stays
    #     the single source of truth. Overwritten ids are vanilla messages that can
    #     never display in our ROM (the prologue slot is never loaded; vanilla Ch1's
    #     scenes are stripped): 0x664 "Renais Castle" location card, 0x90D prologue
    #     opening, 0x914 boss mid-fight line, 0x918 prologue ending. The three quote
    #     msgs (0x936/0x917/0xC25) are the ids the gDefeatTalkList entries in step 5
    #     already reference. Staging mirrors vanilla: protectors left, lead right in
    #     the ending (0x918's Seth/Eirika layout); boss MidRight (0x910's O'Neill).
    fid = {s: _fid_tag(s) for s in (hlin_slot, scram_slot, sephek_slot)}
    # On-map bubbles want vanilla 0x911's Mid pair: with Hlin on plain [OpenLeft],
    # Sephek's MidRight turns AFTER a left turn rendered as empty bubbles (2026-06-10
    # scenes capture); [OpenMidLeft] <-> [OpenMidRight] round-trips are the shape
    # vanilla actually ships on-map.
    opening_staging = {'hlin': ('[OpenMidLeft]', fid[hlin_slot]),
                       'scramsax': ('[OpenFarLeft]', fid[scram_slot]),
                       'sephek': ('[OpenMidRight]', fid[sephek_slot])}
    ending_staging = {'scramsax': ('[OpenMidLeft]', fid[scram_slot]),
                      'hlin': ('[OpenMidRight]', fid[hlin_slot])}
    events = {e['trigger']: e for e in chap.get('events', [])}
    opening_script = events['chapter_start']['script']
    card = next(v for e in opening_script for k, v in e.items()
                if k == 'location_card')
    set_message_body(lines, 0x664, name_message_body(card))
    # The opening splits at Sephek's interrupt into TWO messages (0x90D briefing /
    # 0x90E confrontation), mirroring vanilla's own boss reveal (0x910 is its own
    # message, boss face loaded at message START). A right-side face lazy-loaded
    # MID-message gets empty/offscreen bubbles for its later multi-page turns
    # (2026-06-10 scenes capture) -- vanilla never ships that shape. The event
    # script deploys the enemies between the two, so Sephek's unit appears on the
    # map exactly when he finishes Hlin's sentence.
    i_reveal = next(i for i, e in enumerate(opening_script) if 'sephek' in e)
    set_message_body(lines, 0x90D, _script_to_message(
        opening_script[:i_reveal], opening_staging))
    set_message_body(lines, 0x90E, _script_to_message(
        opening_script[i_reveal:], opening_staging))
    set_message_body(lines, 0x914, _script_to_message(
        events['boss_battle']['script'], opening_staging))
    set_message_body(lines, 0x918, _script_to_message(
        events['chapter_end']['script'], ending_staging))
    set_message_body(lines, 0x936, _script_to_message(
        [{'sephek': by_id['sephek-kaltro']['death_quote']}], opening_staging))
    set_message_body(lines, 0x917, _script_to_message(
        [{'hlin': by_id['hlin-trollbane']['death_quote']}], ending_staging))
    set_message_body(lines, 0xC25, _script_to_message(
        [{'scramsax': by_id['scramsax']['defeat_quote']}], ending_staging))

    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 4b. Give the guest slots a consistent character identity for their deployed class --
    #     just like patch_character_data does for the cast. Guests aren't in PORTRAIT_MAP, so
    #     we align defaultClass + baseLevel + affinity, zero the personal base stats (so stats
    #     == class base), and copy growths + weapon ranks from a class-matched vanilla donor so
    #     each guest fights/levels like a real FE unit of its class and can wield its items.
    #     (Mirrors patch_character_data; keeps the cast and guests on equal footing.)
    _axe = ('PIRATE', 'WARRIOR', 'FIGHTER', 'BRIGAND', 'BERSERKER')
    _hlin_donor = 'CHARACTER_GARCIA' if any(c in hlin_class for c in _axe) else 'CHARACTER_GERIK'
    _scram_donor = 'CHARACTER_GARCIA' if any(c in scram_class for c in _axe) else 'CHARACTER_GERIK'
    # (slot, class, level, donor, female) -- female None means "leave attributes alone"
    # (the boss keeps CA_BOSS; _set_gender would clobber it).
    guest_patch = [(PROLOGUE_HLIN_SLOT, hlin_class, 3, _hlin_donor, True),
                   (PROLOGUE_SCRAMSAX_SLOT, scram_class, 1, _scram_donor, False),
                   (PROLOGUE_SEPHEK_SLOT, 'CLASS_MYRMIDON', 5, 'CHARACTER_JOSHUA', None)]
    with open(CHARACTERS_C, encoding='utf-8') as f:
        chars = f.read()
    for slot, cls, level, donor, female in guest_patch:
        growths, ranks = donor_growths_and_ranks(chars, donor)  # donors are unpatched slots
        marker = '[CHARACTER_%s - 1]' % slot
        s, e = _find_brace_block(chars, marker, CHARACTERS_C)
        block = chars[s:e]
        block = _set_field(block, 'defaultClass', cls, CHARACTERS_C, marker)
        block = _set_field(block, 'affinity', 'UNIT_AFFIN_ANIMA', CHARACTERS_C, marker)
        block = _set_field(block, 'baseLevel', level, CHARACTERS_C, marker)
        if female is not None:
            block = _set_gender(block, female)
        for bf in ('baseHP', 'basePow', 'baseSkl', 'baseSpd', 'baseDef',
                   'baseRes', 'baseLck', 'baseCon'):
            block = _set_field(block, bf, 0, CHARACTERS_C, marker)
        for gf, gv in growths.items():
            block = _set_field(block, gf, gv, CHARACTERS_C, marker)
        block, n = re.subn(r'(\.baseRanks\s*=\s*)\{.*?\}',
                           lambda m: m.group(1) + ranks, block, count=1, flags=re.DOTALL)
        if n == 0:
            sys.exit('ERROR: .baseRanks not found for %s' % marker)
        chars = chars[:s] + block + chars[e:]
    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(chars)

    # 5. All three chapter outcomes ride gDefeatTalkList (vanilla's mechanism -- the flags
    #    on defeat quotes are what set the event flags the Misc AFEVs watch; CA_BOSS alone
    #    sets nothing):
    #    - Sephek: .flag = EVFLAG_DEFEAT_BOSS, exactly like every vanilla boss's entry
    #      (O'Neill/Breguet/...). Without it the DefeatBoss AFEV never fires -- O'Neill's
    #      own entry is keyed to CHAPTER_L_PROLOGUE, not our host slot (caught by the
    #      automated win playtest, 2026-06-09).
    #    - Hlin: .flag = EVFLAG_GAMEOVER (lord-death = game over, decided 2026-06-09;
    #      YAML NOTE 3); CauseGameOverIfLordDies (step 3) fires on it -- vanilla's
    #      Eirika/Duessel mechanism.
    #    - Scramsax: FLAG-LESS quote (vanilla Seth precedent): quote plays, battle
    #      continues, framed as a retreat -- he's alive for Ch1.
    #    msg bodies are written from the chapter YAML in step 4c; #42 generalizes the lord.
    quotes = [(
        '    {\n'
        '        .pid     = CHARACTER_%s, /* Sephek -- boss kill sets the DefeatBoss flag */\n'
        '        .route   = CHAPTER_MODE_ANY,\n'
        '        .chapter = CHAPTER_L_1, /* prologue is hosted on chapter slot 1 */\n'
        '        .flag    = EVFLAG_DEFEAT_BOSS,\n'
        '        .msg     = 0x0936, /* Sephek death quote (YAML death_quote, step 4c) */\n'
        '    },' % sephek_slot), (
        '    {\n'
        '        .pid     = CHARACTER_%s, /* Hlin -- lord-death = game over */\n'
        '        .route   = CHAPTER_MODE_ANY,\n'
        '        .chapter = CHAPTER_L_1, /* prologue is hosted on chapter slot 1 */\n'
        '        .flag    = EVFLAG_GAMEOVER,\n'
        '        .msg     = 0x0917, /* Hlin death quote (YAML death_quote, step 4c) */\n'
        '    },' % hlin_slot), (
        '    {\n'
        '        .pid     = CHARACTER_%s, /* Scramsax -- defeat quote only, NO game over */\n'
        '        .route   = CHAPTER_MODE_ANY,\n'
        '        .chapter = CHAPTER_L_1, /* prologue is hosted on chapter slot 1 */\n'
        '        .msg     = 0x0C25, /* Scramsax retreat quote (YAML defeat_quote, step 4c) */\n'
        '    },' % scram_slot)]
    #    The entries must land at the HEAD of the list: GetDefeatTalkEntry (eventinfo.c)
    #    returns the FIRST match, and vanilla gives every playable slot a generic
    #    chapter=0xFF death quote further down -- NATASHA's/KYLE's would shadow our
    #    flagged entries (quote plays, flag never set, no game over; caught by the
    #    automated gameover playtest, 2026-06-09). Vanilla orders the table the same
    #    way: chapter-keyed boss entries first, generic quotes after. (And never append
    #    after the {.pid = -1} terminator: the scan stops there -- that one was a real,
    #    silent bug too.)
    # 5b. Sephek's mid-fight frost line (slot 4) = a first-engagement boss battle
    #     quote on gBattleTalkList -- FE8's native "mid-fight boss line" mechanism
    #     (vanilla wires O'Neill's 0x916 with this exact two-entry pattern: one for
    #     the player engaging the boss, one for the boss engaging the player; the
    #     EVFLAG_BATTLE_QUOTES flag makes it play exactly once). Same head-insertion
    #     rule as the defeat quotes: GetBattleTalkEntry returns the first match.
    fight_quotes = [(
        '    {\n'
        '        .pidA     = CHAR_EVT_PLAYER_LEADER,\n'
        '        .pidB     = CHARACTER_%s, /* Sephek mid-fight frost line (step 4c) */\n'
        '        .chapter = CHAPTER_L_1,\n'
        '        .flag    = EVFLAG_BATTLE_QUOTES,\n'
        '        .msg     = 0x0914,\n'
        '    },' % sephek_slot), (
        '    {\n'
        '        .pidA     = CHARACTER_%s,\n'
        '        .chapter = CHAPTER_L_1,\n'
        '        .flag    = EVFLAG_BATTLE_QUOTES,\n'
        '        .msg     = 0x0914,\n'
        '    },' % sephek_slot)]
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n'
    fight_head = 'CONST_DATA struct BattleTalkExtEnt gBattleTalkList[] = {\n'
    if bq.count(head) != 1 or bq.count(fight_head) != 1:
        sys.exit('ERROR: talk-list heads not in expected vanilla form in %s'
                 % BATTLEQUOTES_C)
    bq = bq.replace(head, head + '\n'.join(quotes) + '\n')
    bq = bq.replace(fight_head, fight_head + '\n'.join(fight_quotes) + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)

    # 6. Opening montage (#43): when MONTAGE=1, re-render the intro-monologue slides as our
    #    lore crawl + the world-map tour. The boot cut + New-Game redirect themselves (so the
    #    prologue loads through host chapter slot 1, dodging the prologue slot's special-cased
    #    HUD/terrain handling) are the single owner _configure_boot()'s job, called once from
    #    main() -- MONTAGE=1 there keeps the intro monologue for these slides to replace.
    if montage:
        print('opening montage (#43):')
        inject_opening_montage(campaign, verbose=verbose)
        inject_world_tour(campaign, verbose=verbose)

    # 7. Don't start in tutorial mode. New Game sets PLAY_FLAG_TUTORIAL (gamecontrol.c
    #    sub_8009C5C), which drives the vanilla guide/tutorial system; our beginning scene
    #    is a plain deploy with none of that setup, so clear the flag.
    with open(GAMECONTROL_C, encoding='utf-8') as f:
        gc = f.read()
    gc, n = re.subn(r'[ \t]*gPlaySt\.chapterStateBits \|= PLAY_FLAG_TUTORIAL;\n',
                    '', gc, count=1)
    if n == 0:
        sys.exit('ERROR: PLAY_FLAG_TUTORIAL set not found in %s' % GAMECONTROL_C)
    with open(GAMECONTROL_C, 'w', encoding='utf-8') as f:
        f.write(gc)

    if verbose:
        print('  prologue map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d '
              '(Ch1 group); New Game redirects %d -> %d'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, PROLOGUE_HOST_INDEX,
                 PROLOGUE_CHAPTER_INDEX, PROLOGUE_HOST_INDEX))
        print('  units: Hlin(%s)+Scramsax(%s) vs Sephek(%s)+2 guards'
              % (hlin_slot, scram_slot, sephek_slot))


def _load_chapter_yaml(campaign, filename):
    path = os.path.join(REPO, 'campaigns', campaign, 'chapters', filename)
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


# --- Shared chapter-injection helpers (#104): hoisted from inject_ch01/inject_ch02 ---
# so ch03+ reuse them instead of growing new copy-paste siblings. Pure string/file
# mechanics only -- everything chapter-specific rides in as an argument.

def _split_script_beats(script, card_required=True):
    """Split a locked chapter-YAML cutscene `script:` into (location_card, beats):
    entries accumulate into the current beat, `beat_break` sentinels start a new one,
    and the `location_card` rides out separately (card_required=False tolerates a
    script without one and returns card=None)."""
    if card_required:
        card = next(v for e in script for k, v in e.items() if k == 'location_card')
    else:
        card = next((v for e in script for k, v in e.items()
                     if k == 'location_card'), None)
    beats = [[]]
    for entry in script:
        (k, v), = entry.items()
        if k == 'location_card':
            continue
        if k == 'beat_break':
            beats.append([])
            continue
        beats[-1].append(entry)
    return card, beats


def _split_event_beats(chap, trigger, err_label, msg_ids=None, card_required=True):
    """Locate the chapter event with `trigger` and split its locked `script:` into
    (location_card, beats) (cf. _split_script_beats). Passing the scene's reserved
    `msg_ids` block guards the split against it -- a count mismatch means a
    beat_break drifted in the YAML and a zip would silently drop the extra."""
    ev = next((e for e in chap['events'] if e.get('trigger') == trigger), None)
    if ev is None:
        sys.exit('ERROR: %s: no %r event in the chapter YAML' % (err_label, trigger))
    card, beats = _split_script_beats(ev['script'], card_required=card_required)
    if msg_ids is not None and len(beats) != len(msg_ids):
        sys.exit('ERROR: %s split into %d beats; expected %d (check beat_break '
                 'markers in the YAML)' % (err_label, len(beats), len(msg_ids)))
    return card, beats


def _cutscene_fid(spk, special, err_label, fallback=None):
    """Speaker id -> face tag for a chapter cutscene: the chapter's `special` speakers
    first (guest slots, faceless `narration` -> None), then the PC PORTRAIT_MAP, then
    an optional `fallback` portrait map (e.g. GUEST_PORTRAIT_MAP) checked LAST."""
    if spk in special:
        return special[spk]
    if spk in PORTRAIT_MAP:
        return _fid_tag(PORTRAIT_MAP[spk].upper())
    if fallback and spk in fallback:
        return _fid_tag(fallback[spk].upper())
    sys.exit('ERROR: %s %r' % (err_label, spk))


def _make_fid(special, err_label, fallback=None):
    """A chapter's speaker->face function (a closure over _cutscene_fid), the shape
    _stage_beat/_emit_scene_beats consume."""
    def fid(spk):
        return _cutscene_fid(spk, special, err_label, fallback=fallback)
    return fid


def _stage_beat(beat, fid, home, overrides=None):
    """Podium staging for one scenic beat: speaker -> (podium, face tag). Speakers
    default to the mid-left podium; `home` anchors recurring speakers (quest-givers),
    `overrides` moves a speaker for this beat only; faces resolve through the
    chapter's fid function (cf. _cutscene_fid)."""
    ov = overrides or {}
    return {k: (ov.get(k, home.get(k, '[OpenMidLeft]')), fid(k))
            for e in beat for k in e}


def _emit_scene_beats(lines, msg_ids, beats, fid, home, overrides=None,
                      preloads=None, width=None, trailings=None):
    """Write one message per scenic beat (staging via _stage_beat, body via
    _script_to_message). width=None picks per beat: faceless-narration beats ride
    the opaque, auto-centered SOLOTEXTBOXSTART box (#58) wrapped at the on-map 28
    (42 overflows the centered box); faced beats use the full-screen scenic 42.
    A fixed width (e.g. 42) overrides for scenes with no narration beats.
    `trailings` (parallel to beats) appends a raw text-code to a beat's body -- see
    _script_to_message's `trailing` (the single-face-exit fade)."""
    overrides = overrides or [None] * len(beats)
    preloads = preloads or [None] * len(beats)
    trailings = trailings or [None] * len(beats)
    if not (len(overrides) == len(preloads) == len(trailings) == len(beats)):
        sys.exit('ERROR: scene staging lists out of step with its %d beats '
                 '(%d overrides, %d preloads, %d trailings) for msgs %s' %
                 (len(beats), len(overrides), len(preloads), len(trailings), msg_ids))
    for msg_id, beat, override, preload, trailing in zip(
            msg_ids, beats, overrides, preloads, trailings):
        # Faced scene beats render via _scenic_beat_calls -> Text() -> a TALK BUBBLE (PutTalkBubble),
        # NOT a full-screen box -- and a bubble line over 29 tiles hits the unclamped x = 29 - width
        # < 0 branch and overflows off the right edge (the ch03 crier "...pays fifty gold to whoever
        # cle|" bug). So faced beats must wrap at the map-bubble 29 (the entrance line already does);
        # narration keeps the 28 that fits the auto-centered SOLOTEXTBOXSTART.
        w = width if width is not None else (28 if _beat_is_narration(beat) else 29)
        set_message_body(lines, msg_id, _script_to_message(
            beat, _stage_beat(beat, fid, home, override), width=w, preload=preload,
            trailing=trailing))


# Vendored tileset -> _register_tileset label stem. A chapter map's tileset comes
# from its layout .json (stamped by the editor-export/import pipeline), so the map
# can never silently register against the wrong tileset's gfx/palette/terrain.
# 'port-or-town-winter' is ch05's (#25). The stem is claimed here so _register_chapter_map
# resolves it; the _register_tileset call that actually writes the asset entries lands with
# inject_ch05, the same way 'Cave' rides inject_ch03.
TILESET_STEMS = {'snowy-bern': 'Snow', 'cave-interior': 'Cave',
                 'port-or-town-winter': 'PortTown'}


def _register_chapter_map(maps_dir, layout, comment):
    """Copy a painted chapter layout (maps/<stem>.{mar,json}) into the decomp, register
    its incbin in CONST_MAPS_S under `comment` + a fresh gChapterDataAssetTable slot,
    and return the (obj, pal, cfg, layout) asset indices for the layout's OWN tileset
    (read from its .json; absent = the legacy snowy-bern maps). The tileset must
    already be registered -- Snow rides inject_winter_tileset, Cave lands with the
    ch03 injector; an unregistered label sys.exits by name in _asm_table_word_index."""
    label, stem = layout
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (label, ext)))
    with open(os.path.join(maps_dir, '%s.json' % stem), encoding='utf-8') as f:
        tileset = json.load(f).get('tileset', WINTER_TILESET)
    if tileset not in TILESET_STEMS:
        sys.exit('ERROR: %s.json names tileset %r -- add it to TILESET_STEMS and '
                 'register it (_register_tileset) first' % (stem, tileset))
    ts = TILESET_STEMS[tileset]
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* %s */' % comment,
            '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % label]) + '\n')
    layout_idx = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [label])
    obj_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                    'ObjectType%s' % ts)
    pal_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                    'MapPalette%s' % ts)
    cfg_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                    'TileConfiguration%s' % ts)
    return obj_idx, pal_idx, cfg_idx, layout_idx


def _retarget_host_chapter(host_index, goal_slot, goal_type, goal_err, indices,
                           chapter_number, event_group, goal_text_ids):
    """Point host chapter slot `host_index` (chapter_settings.json) at a registered
    map (`indices` from _register_chapter_map) and copy vanilla slot `goal_slot`'s
    goal template (checked against windowDataType `goal_type`, else sys.exit(goal_err)).
    The prep-screen header reads "Chapter NN" from prepScreenNumber, not the slot
    index. It is a double-wide glyph index: vanilla slots carry exactly 2 * chapter
    number (slot1=2, slot2=4, ... both ch5 and ch5x = 10). Returns the host dict.

    `event_group` is the ChapterEventGroup SYMBOL the caller's injector fills, and it is
    mandatory because the slot's own mapEventDataId cannot be trusted to name it: FE8
    inserts chapter 5X at slot 5, so from there on the slot index stops tracking the
    chapter number (slot 5 -> Ch5XEvents, while ch04's events live in Ch5EventData).
    Retargeting only the map ids is enough to make the chapter LOOK right, so a wrong
    event group fails silently and totally -- the slot presents our map while running the
    host slot's roster and scripts. Repointing it here keeps map and events one decision.

    `goal_text_ids` = (windowTextId, statusObjectiveTextId) the chapter OWNS. They override the
    donor's, which are shared across vanilla slots and were being inherited (#207)."""
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    host = settings['chapters'][host_index]
    goal = settings['chapters'][goal_slot]['goal']
    if goal.get('windowDataType') != goal_type:
        sys.exit(goal_err)
    host['map'].update({'obj1Id': obj_idx, 'obj2Id': 0, 'paletteId': pal_idx,
                        'tileConfigId': cfg_idx, 'mainLayerId': layout_idx,
                        'objAnimId': 0, 'paletteAnimId': 0, 'changeLayerId': 0})
    host['mapEventDataId'] = _asm_table_word_index(
        ASSET_TABLE_S, 'gChapterDataAssetTable', event_group)
    host['goal'] = dict(goal)
    # The donor's goal carries the donor's TEXT ids, and vanilla points many slots at one string
    # -- so copying it wholesale makes two hosted chapters write over each other's objective
    # (#207). ch04's donor is even ch02's own host slot. The caller declares its pair and it wins
    # here, alongside the map and event ids, so all three stay ONE decision.
    host['goal']['windowTextId'], host['goal']['statusObjectiveTextId'] = goal_text_ids
    host['prepScreenNumber'] = chapter_number * 2
    # fadeToBlack=1: the chapter INTRO ends on BLACK instead of fading the battle map in
    # (ChapterIntro_LoopFadeToMap, chapterintrofx.c:916 -- fadeToBlack takes the SetDispEnable
    # black branch, else it blends the map in). Our openings are BG cutscenes (the BeginningScene
    # BACGs), so the vanilla map fade-in just FLASHES the map for a beat before the BACG. This is
    # the vanilla mechanism for cutscene-opening chapters (slots 2/3 already ship with it; slot 4
    # did not -> ch03's opening map flash). Set for every hosted chapter so none flash.
    host['fadeToBlack'] = 1
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    return host


def recruit_chapter_number(campaign, unit):
    """The chapter_number a cast member is RECRUITED in, or None for the founding party.
    Data-driven from the unit YAML `recruit.chapter` (a chapter id) -> that chapter's
    `chapter_number`. The reusable recruit infra keys prep-availability off this: a unit
    is on the field from the chapter AFTER it is recruited (see cast_available_at)."""
    rec = (unit.get('recruit') or {}).get('chapter')
    if not rec:
        return None
    return _load_chapter_yaml(campaign, rec + '.yaml')['chapter_number']


def recruit_initial_faction(unit):
    """The faction an on-map talk recruit is PLACED as before it joins -- the reusable
    discriminator between the two recruit flavours (both end at BLUE via CUSA on talk):
      GREEN (default) -- a neutral bystander recruited in place (Colm/Neimi; our Trex, Basil).
      RED             -- a hostile unit talked down mid-fight (vanilla Joshua/Marisa; our
                         Lupin, Sahnar), opt-in via the unit YAML `recruit.initial_faction: red`.
    Returns the FE8 event faction token ('GREEN'|'RED'). Keeps the recruit path faction-
    parameterized so every chapter reuses ONE flow instead of a bespoke green/red copy."""
    faction = (unit.get('recruit') or {}).get('initial_faction', 'green')
    token = str(faction).upper()
    if token not in ('GREEN', 'RED'):
        sys.exit('ERROR: %s recruit.initial_faction must be green or red, got %r'
                 % (unit.get('id', '?'), faction))
    return token


def _classed_cast(campaign, available_at=None):
    """The classed cast in PORTRAIT_MAP order: (unit_id, slot, class_enum,
    deploy_class_enum, level) per unit, plus a parallel display-name list.
    Units with no class mapping (non-combat NPCs) are skipped.

    available_at=N (a chapter_number) returns only the cast ON THE FIELD at chapter N =
    the founding party (no `recruit:` block) + every recruit whose recruit chapter is
    BEFORE N (they joined in a prior chapter, so they ride the prep/deploy roster). A unit
    recruited IN chapter N is NOT here -- it enters mid-chapter via inject_recruits (green
    placement + a CUSA join), not the prep roster. available_at=None returns the full cast
    (recruits included), which still drives name/class/stat patching, map sprites and death
    quotes regardless of chapter."""
    cast, names = [], []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if available_at is not None:
            rc = recruit_chapter_number(campaign, unit)
            if rc is not None and rc >= available_at:
                continue   # not yet recruited (or joins THIS chapter mid-map)
        cast.append((unit_id, slot, class_enum, deploy_class_for(unit),
                     int(unit.get('fe_stats', {}).get('level', 1))))
        names.append(display_name(unit))
    if not cast:
        sys.exit('ERROR: no classed cast -- every PORTRAIT_MAP unit is missing a '
                 'class mapping (check the pcs/*.yaml fe_stats blocks)')
    return cast, names


# A recruit placed GREEN on the map in its OWN recruit chapter (a Colm-style talk recruit,
# e.g. Trex: recruit.via == 'story') self-joins the blue party via CUSA when talked to, so it
# persists to the next chapter with no extra wiring. Every OTHER recruit joins OFF the map --
# a cutscene/market recruit, e.g. Baxby (recruit.via == 'market'), won over in a scene with no
# on-map unit -- so NOTHING puts it in the saved party. cast_available_at() only SIZES the
# deploy cap template (never LOADed), so an off-map recruit would silently be absent from the
# field until it gets an explicit between-chapter join-LOAD (#23). This is that discriminator.
ON_MAP_RECRUIT_VIA = ('story', 'talk')   # placed green + CUSA -> self-joins, persists naturally


def offmap_join_recruits(campaign, chapter_number):
    """Cast members that FIRST enter the persistent party OFF the map at `chapter_number`:
    recruits whose recruit chapter is the one immediately before (so cast_available_at first
    lists them now) and whose join method is off-map (recruit.via not in ON_MAP_RECRUIT_VIA).
    Returns [(unit_id, slot, class_enum, deploy_class_enum, level)], PORTRAIT_MAP order.

    Each such unit needs a beginning-scene LOAD1 so it enters the saved roster -- the prep
    availability filter only sizes the deploy cap; it never LOADs anyone. Keyed to the
    immediately-preceding chapter (contiguous hosted chapters, our MVP) so a unit is joined
    exactly once, the first chapter it rides the prep roster (no re-LOAD -> no duplicate)."""
    out = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        rc = recruit_chapter_number(campaign, unit)
        if rc is None or rc != chapter_number - 1:
            continue   # not a recruit, or not newly available at THIS chapter
        via = (unit.get('recruit') or {}).get('via')
        if via in ON_MAP_RECRUIT_VIA:
            continue   # on-map talk recruit -- self-joins via CUSA, persists naturally
        out.append((unit_id, slot, class_enum, deploy_class_for(unit),
                    int(unit.get('fe_stats', {}).get('level', 1))))
    return out


def char_symbol(slot):
    """The CHARACTER_ enum for a vanilla character slot name (the unit's on-map pid/FID
    symbol). A cast PC rides its PORTRAIT_MAP slot, so its map identity is CHARACTER_<slot>."""
    return 'CHARACTER_%s' % slot.upper()


def on_map_talk_recruits(campaign, chapter_number):
    """Cast members recruited MID-MAP via Talk IN `chapter_number` (the mirror of
    offmap_join_recruits): recruits whose recruit chapter IS this chapter and whose join
    method is an on-map talk (recruit.via in ON_MAP_RECRUIT_VIA). Returns
    [(unit_id, slot, class_enum, deploy_class_enum, level)] in PORTRAIT_MAP order. Each is
    placed GREEN and joined by a CHAR talk -> CUSA (the vanilla Colm/Neimi pattern, #23 item 2)."""
    out = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if recruit_chapter_number(campaign, unit) != chapter_number:
            continue   # not recruited in THIS chapter
        if (unit.get('recruit') or {}).get('via') not in ON_MAP_RECRUIT_VIA:
            continue   # off-map recruit -- joins via offmap_join_recruits, not an on-map talk
        out.append((unit_id, slot, class_enum, deploy_class_for(unit),
                    int(unit.get('fe_stats', {}).get('level', 1))))
    return out


def talk_recruiters(campaign, chapter_number):
    """The candidate RECRUITERS for an on-map talk recruit in chapter N = every core party
    member on the blue field roster (cast_available_at(N) = _classed_cast(available_at=N)),
    as CHARACTER_ symbols. "Talker = ANY core party member" (Nicolas, 2026-07-08: the only
    thief must be non-missable, and a static CHAR can't name the CHOSEN lord) -> one CHAR
    entry per candidate, all -> the shared recruit script."""
    cast, _ = _classed_cast(campaign, available_at=chapter_number)
    return [char_symbol(slot) for _, slot, *_ in cast]


def talk_recruit_char_entries(recruiters, target, flag, script):
    """One CHAR(flag, script, recruiter, target) per recruiter -- FE8's multi-recruiter talk
    idiom (cf. vanilla ch14a Rennac: two CHAR entries sharing a flag). All share flag + script
    + target, so ANY recruiter's talk recruits `target` and completing it sets the shared flag,
    disabling every entry (no re-trigger)."""
    return ''.join('    CHAR(%s, %s, %s, %s)\n' % (flag, script, r, target)
                   for r in recruiters)


def talk_recruit_script(msg_id, target, pre_script=''):
    """The shared talk-recruit script (cf. vanilla EventScr_Ch3_Talk_NeimiColm): show the
    migrated talk line, then CUSA `target` to BLUE (EvtChangeFaction), set the map-event
    visibility evbit, end. MUSS/STAL are trimmed -- the line rides the map talk window, not a
    fanfare. Faction-agnostic: a GREEN bystander (Trex/Basil) and a RED parley (Lupin/Sahnar)
    both end at BLUE via this one CUSA. `pre_script` is spliced in AFTER the talk line and
    BEFORE the CUSA -- a group parley passes its own conversion sweep there (ch04: the wolf
    pack, convert_survivors_green), so the whole outcome still rides the single recruit path."""
    return ('{\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X)\n'
            '    TEXTEND\n'
            '    REMA\n' % msg_id
            + pre_script
            + '    CUSA(%s) /* -> blue: the talk recruits the target */\n'
              '    EVBIT_T(7)\n'
              '    ENDA\n}' % target)


def talk_recruit_wiring(recruiters, target, flag, script_symbol, msg_id, pre_script=''):
    """Assemble the reusable on-map talk-recruit event wiring (ch03 Trex / ch04 Lupin / ch05
    Basil+Sahnar). Returns (char_events, talk_script):
      char_events -- the EventListScr_..._Character body: one CHAR(flag, script, recruiter,
        target) per `recruiters` entry (talk_recruit_char_entries). ch03 passes the whole
        field roster (talk_recruiters -- "any party member"); ch04 passes a single recruiter
        (the YAML parley.by, e.g. Marty) -- same machinery, caller picks the recruiter set.
      talk_script -- the shared talk script (talk_recruit_script) whose CUSA flips `target`
        BLUE, with `pre_script` spliced in before the CUSA (the red parley's pack conversion).
    Both flavours share ONE flow instead of a per-chapter green/red copy."""
    char_events = ('{\n' + talk_recruit_char_entries(recruiters, target, flag, script_symbol)
                   + '    END_MAIN\n}')
    return char_events, talk_recruit_script(msg_id, target, pre_script=pre_script)


def midmap_minibosses(chap):
    """Enemy units in a loaded chapter flagged `is_miniboss` -- a mid-map miniboss whose
    DEFEAT fires a flagged death cutscene (the mirror of the boss's DefeatBoss win, but keyed
    to a tmp flag + a Misc AFEV rather than EVFLAG_DEFEAT_BOSS). Returns the enemy dicts in
    YAML order. ch03's Icewind Brute triggers the RBG-execution beat (#23 item 1)."""
    return [e for e in chap.get('enemy_units', []) if e.get('is_miniboss')]


def flag_defeat_quote(pid, chapter_const, flag, comment):
    """A SILENT (msg=0) gDefeatTalkList entry keying `pid`'s death in `chapter_const` to `flag`.
    SetPidDefeatedFlag sets the flag on ANY matching pid's death (no CA_BOSS gate, eventinfo.c),
    while DisplayDefeatTalkForPid suppresses the quote because msg=0 -- so a faceless unit sets
    an event flag without rendering a boxless, unreadable line. Shared by the ch03 boss WIN
    (flag=EVFLAG_DEFEAT_BOSS -> the DefeatBoss AFEV) and the Brute miniboss's mid-map death
    trigger (flag=a tmp flag watched by a Misc AFEV)."""
    return ('    {\n'
            '        .pid     = %s, /* %s */\n'
            '        .route   = CHAPTER_MODE_ANY,\n'
            '        .chapter = %s,\n'
            '        .flag    = %s,\n'
            '        .msg     = 0,\n'
            '    },' % (pid, comment, chapter_const, flag))


def midmap_afev(guard_flag, script, watch_flag):
    """A Misc AFEV that runs `script` once when `watch_flag` is set (the miniboss's flagged
    death), guarded by `guard_flag` (EvCheck01_AFEV's ent-flag, set after the entry fires) so it
    does not re-trigger every subsequent turn. The vanilla mid-map death-scene idiom (cf. ch1
    AFEV(EVFLAG_TMP(7), EventScr_Ch1_Misc_DefeatBoss, EVFLAG_DEFEAT_BOSS)). guard_flag must
    differ from watch_flag."""
    return 'AFEV(%s, %s, %s)' % (guard_flag, script, watch_flag)


def _ally_unit_entry(leader, slot, class_enum, level, x, y, items, comment,
                     allegiance='BLUE', autolevel=False, ai=None, char=None):
    """One non-RED UnitDefinition row (events_udefs.c) for a chapter join/deploy/
    green-ally table. leader=None omits the leaderCharIndex field; autolevel/ai
    toggle their optional lines (GREEN allies use all three). `char` overrides the
    charIndex with a raw pid (a generic green pack shares one pid); default derives it
    from the named cast `slot`."""
    charref = char if char is not None else 'CHARACTER_%s' % slot.upper()
    fields = ['.charIndex = %s,%s' % (charref, comment),
              '.classIndex = %s,' % class_enum]
    if leader:
        fields.append('.leaderCharIndex = %s,' % leader)
    if autolevel:
        fields.append('.autolevel = 1,')
    fields += ['.allegiance = FACTION_ID_%s,' % allegiance,
               '.level = %d,' % level,
               '.xPosition = %d,' % x,
               '.yPosition = %d,' % y,
               '.redaCount = 0,',
               '.items = { %s },' % items]
    if ai:
        fields.append('.ai = %s,' % ai)
    return '    {\n' + ''.join('        %s\n' % f for f in fields) + '    },'


def _deploy_cap_entries(chap, cast, leader, label):
    """The ally deploy "cap template" rows from the chapter's `deployment:` block
    (#107 schema): never LOADed -- the prep flow reads the table's entry count as
    the field cap and its coords as the deploy tiles. classIndex rides
    deploy_class_for (today == the plain vanilla class; custom anims need no clone
    class since the per-character _u25 path, #65 M-B)."""
    dep = chap.get('deployment') or {}
    slots, limit = dep.get('deploy_slots'), dep.get('deploy_limit')
    if not slots:
        sys.exit('ERROR: %s has no deployment.deploy_slots -- a hosted chapter '
                 'needs its deploy tiles authored (they land with the map paint)'
                 % label)
    if len(slots) != limit:
        sys.exit('ERROR: %s deployment.deploy_slots (%d) != deploy_limit (%s)'
                 % (label, len(slots), limit))
    if len(cast) < limit:
        sys.exit('ERROR: %d classed cast < %s deploy_limit %d'
                 % (len(cast), label, limit))
    return [_ally_unit_entry(leader, slot, dce, lv, x, y, '0',
                             ' /* deploy slot %d (cap template, never LOADed) */' % i)
            for i, ((uid, slot, ce, dce, lv), (x, y))
            in enumerate(zip(cast[:limit], slots))]


def _enemy_unit_entry(char, class_enum, level, autolevel, x, y, items, ai, comment,
                      itemdrop=False):
    """One enemy UnitDefinition row; autolevel/itemdrop toggle their optional fields."""
    return ('    {\n'
            '        .charIndex = %s,%s\n'
            '        .classIndex = %s,\n'
            '%s'
            '        .allegiance = FACTION_ID_RED,\n'
            '        .level = %d,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '%s'
            '        .items = { %s },\n'
            '        .ai = %s,\n'
            '    },' % (char, comment, class_enum,
                       '        .autolevel = 1,\n' if autolevel else '',
                       level, x, y,
                       '        .itemDrop = 1,\n' if itemdrop else '',
                       items, ai))


EVENTCALL_H = os.path.join(DECOMP, 'include', 'eventcall.h')

# Every campaign-owned UnitDefinition table carries this prefix. It is the whole point of
# declare_unit_table: a symbol's NAME should say whose data is in it.
MS_TABLE_PREFIX = 'MS_'


def declare_unit_table(symbol, rows, comment):
    """DEFINE a campaign-owned UnitDefinition table, and return its symbol.

    Our chapter rosters used to be written by block-overwriting a vanilla table that the
    host slot's stripped cutscenes had left unreferenced -- ch04's moose still rides a
    symbol our own source comments as "dead Ch5 unit table". That worked, but it has two
    real costs, and the second one is what retires it:

      1. The symbol's NAME LIES. `UnitDef_088B61A8` holds ch05's sixteen tomb-guardians;
         nothing about the name says so, and the vanilla chapter it is named for is not
         even the vanilla chapter ch05 is a retile of. Reading the injector meant holding
         two unrelated numbering offsets in your head -- ours (chapter N hosts on slot
         N+1, because the prologue occupies a real slot) and FE8's own (it inserted Ch5X
         at slot 5, so from slot 6 on the slot index and the symbol name disagree in the
         BASE GAME: slot 6 ships Ch5EventData, slot 7 ships Ch6Events).
      2. It rations us to whatever the host slot happens to leave unreferenced. Slot 5
         freed seven tables; slot 6 frees three, and ch05 needs seven. Squatting would
         have meant reaching into Ch6's world-map ENCOUNTER rosters -- borrowing storage
         from a system we simply hope never runs.

    Defining our own symbol costs one appended table plus one extern, removes the ration
    entirely, and leaves the vanilla table untouched and honestly named. Both files are in
    PATCHED_DECOMP_FILES, so they are restored from HEAD each build and these appends never
    accumulate across builds.

    The host slot's EVENT-LIST symbols (EventListScr_ChN_*, the ChapterEventGroup) are NOT
    covered by this and cannot be: chapter_settings.json points at them structurally. Those
    stay vanilla-named, named once in a per-chapter constant block, and nowhere else.
    """
    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    # The decomp files are restored from HEAD each build, so a symbol already present means
    # two injectors picked the same name in ONE run -- a collision that would otherwise
    # surface as a duplicate-definition link error a long way from its cause.
    if ('struct UnitDefinition %s[]' % symbol) in udefs:
        sys.exit('ERROR: unit table %s is already defined this build -- two injectors are '
                 'claiming one symbol name' % symbol)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(unit_table_definition(udefs, symbol, rows, comment))
    with open(EVENTCALL_H, encoding='utf-8') as f:
        header = f.read()
    with open(EVENTCALL_H, 'w', encoding='utf-8') as f:
        f.write(unit_table_extern(header, symbol, comment))
    return symbol


def point_event_group_at(info, group, field, symbol):
    """Pure: `info` (a chN-eventinfo.h) with ChapterEventGroup `group`.`field` -> `symbol`.

    Declaring our own roster table is only half the job: the ENGINE reads the roster through
    the ChapterEventGroup, so a table nobody points at is inert and the slot quietly keeps
    using the vanilla one. That is not a hypothetical -- it shipped for one build of ch05 and
    put the party on vanilla Ch6's start tiles, four of them inside walls, on a map whose
    geometry is vanilla Ch5's. Nothing failed: PREP ran, the map drew, the scenario PASSed,
    and only a unit-position dump showed it (INSPECT.units, added for exactly this).

    ch03/ch04 never hit it because they block-overwrote the very table the group already
    pointed at, so the link could not come undone. Owning the symbol means owning the pointer
    too, and this is the half that has no symptom.
    """
    pattern = re.compile(r'(\.%s\s*=\s*)([A-Za-z_]\w*)' % re.escape(field))
    body_start = info.index('struct ChapterEventGroup %s = {' % group)
    body_end = info.index('};', body_start)
    head, body, tail = info[:body_start], info[body_start:body_end], info[body_end:]
    body, n = pattern.subn(lambda m: m.group(1) + symbol, body)
    if n == 0:
        sys.exit('ERROR: ChapterEventGroup %s has no .%s field to repoint' % (group, field))
    return head + body + tail


def assert_event_group_roster(info_path, group, symbol):
    """Fail the BUILD if `group` does not deploy `symbol` on both difficulties.

    The bug this closes has no symptom: a chapter whose group still points at the vanilla
    ally table boots, runs PREP, draws the map, deploys a party and PASSes a load-test --
    just on another map's coordinates. It is the ally-table twin of the host-slot/event-group
    mis-target in docs/adding-a-chapter.md step 4, and it cost a build here.
    """
    with open(info_path, encoding='utf-8') as f:
        info = f.read()
    body = info[info.index('struct ChapterEventGroup %s = {' % group):]
    body = body[:body.index('};')]
    for field in ('playerUnitsInNormal', 'playerUnitsInHard'):
        match = re.search(r'\.%s\s*=\s*([A-Za-z_]\w*)' % field, body)
        if not match:
            sys.exit('ERROR: %s has no .%s' % (group, field))
        if match.group(1) != symbol:
            sys.exit('ERROR: %s.%s deploys %s, not %s -- the chapter would field its roster '
                     'on the HOST SLOT\'s tiles, which belong to a different map. Declaring '
                     'a roster table does not wire it; point_event_group_at does.'
                     % (group, field, match.group(1), symbol))


def declare_event_script(path, symbol, body, comment):
    """DEFINE a campaign-owned EventListScr in `path` (a chN-eventscript.h), and return its symbol.

    The script twin of declare_unit_table, for the same reason and with the same payoff. A host
    slot frees only the scripts its stripped cutscenes stop referencing -- slot 6 leaves five, and
    ch05 needs three reinforcement waves plus one per village, which is more than it has. Naming
    our own removes the budget entirely, and `MS_Ch05Village2` says what it runs where
    `EventScr_089F2AE4` says nothing at all.
    """
    with open(path, encoding='utf-8') as f:
        script = f.read()
    if ('EventListScr %s[]' % symbol) in script:
        sys.exit('ERROR: event script %s is already defined this build -- two injectors are '
                 'claiming one symbol name' % symbol)
    _assert_ms_symbol(symbol)
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n/* %s */\nCONST_DATA EventListScr %s[] = %s;\n' % (comment, symbol, body))
    with open(EVENTCALL_H, encoding='utf-8') as f:
        header = f.read()
    with open(EVENTCALL_H, 'w', encoding='utf-8') as f:
        f.write(event_script_extern(header, symbol, comment))
    return symbol


def assert_event_scripts_defined(path, symbols):
    """Fail the BUILD if a declared event script is missing from `path`.

    `declare_event_script` APPENDS, while the injectors' block-replacements rewrite the same file
    wholesale from a copy read earlier -- so declaring before the bulk write silently discards
    every appended script. The Location list still names them and the externs still exist, so the
    only symptom is a link error pointing at the reference rather than at the loss. Cheap to
    assert, and it pins the ordering against a future reshuffle of the injector.
    """
    with open(path, encoding='utf-8') as f:
        script = f.read()
    missing = [s for s in symbols if ('EventListScr %s[]' % s) not in script]
    if missing:
        sys.exit('ERROR: %s declared but not defined in %s -- declare_event_script APPENDS, so it '
                 'must run AFTER the block-replacement pass rewrites the file, never before'
                 % (', '.join(missing), os.path.basename(path)))


# Anchored on the first EventListScr extern, like the UnitDefinition block above it.
_SCRIPT_EXTERN_ANCHOR = 'extern CONST_DATA EventListScr EventScr_9EEA58[];'


def event_script_extern(header, symbol, comment):
    """Pure: `header` (eventcall.h) with an extern for event script `symbol`. Idempotent.

    The Location list that names these lives in a DIFFERENT file from their definitions, so
    without the declaration agbcc sees an implicit int and the build dies a long way from here.
    """
    _assert_ms_symbol(symbol)
    decl = 'extern CONST_DATA EventListScr %s[];' % symbol
    if decl in header:
        return header
    if _SCRIPT_EXTERN_ANCHOR not in header:
        sys.exit('ERROR: eventcall.h has no EventListScr extern block to extend (looked for %r)'
                 % _SCRIPT_EXTERN_ANCHOR)
    return header.replace(_SCRIPT_EXTERN_ANCHOR,
                          '%s\n%s /* %s */' % (_SCRIPT_EXTERN_ANCHOR, decl, comment), 1)


def unit_table_definition(udefs, symbol, rows, comment):
    """Pure: `udefs` with a campaign-owned UnitDefinition table appended.

    The rows are the same `_ally_unit_entry` / `_enemy_unit_entry` strings a squatted
    vanilla table took, so nothing about roster construction changes -- only where the
    result lands and what it is called.
    """
    _assert_ms_symbol(symbol)
    body = '{\n' + '\n'.join(rows) + '\n    { 0 },\n}'
    return udefs + ('\n/* %s */\nCONST_DATA struct UnitDefinition %s[] = %s;\n'
                    % (comment, symbol, body))


# agbcc needs a declaration before the event script that names the table. The vanilla tables
# declare theirs in eventcall.h, so ours sit with them rather than in a new header nothing
# else includes. Anchored on the FIRST UnitDefinition extern -- appending after a "last"
# extern found by scanning is what breaks when the block grows.
_UDEF_EXTERN_ANCHOR = 'extern CONST_DATA struct UnitDefinition UnitDef_Event_PrologueAlly[];'


def unit_table_extern(header, symbol, comment):
    """Pure: `header` (eventcall.h) with an extern for `symbol`. Idempotent."""
    _assert_ms_symbol(symbol)
    decl = 'extern CONST_DATA struct UnitDefinition %s[];' % symbol
    if decl in header:
        return header
    if _UDEF_EXTERN_ANCHOR not in header:
        sys.exit('ERROR: eventcall.h has no UnitDefinition extern block to extend '
                 '(looked for %r)' % _UDEF_EXTERN_ANCHOR)
    return header.replace(_UDEF_EXTERN_ANCHOR,
                          '%s\n%s /* %s */' % (_UDEF_EXTERN_ANCHOR, decl, comment), 1)


def chapter_label_constants(source=None):
    """{slot index: CHAPTER_L_* name} read from the decomp's own chapters.h.

    The name and the value DIVERGE, and quietly. FE8 inserted Ch5x at slot 5, so:

        CHAPTER_L_4  = 0x04     CHAPTER_L_5X = 0x05
        CHAPTER_L_5  = 0x06     CHAPTER_L_6  = 0x07

    Slot 6 is therefore CHAPTER_L_5, and every chapter we host from here on has a label
    whose digits are one less than its slot. For slots 1-4 the two coincide, which is why
    four injectors could hardcode 'CHAPTER_L_%d' % host_index and be right by accident.

    ch05 is the first chapter where guessing is WRONG, and the failure is silent: a
    gDefeatTalkList entry keyed to the wrong .chapter simply never matches, so the boss dies,
    no flag is set, DefeatBoss never fires, and the map cannot be won -- with nothing in the
    build or the logs to say why. Resolve by VALUE; never spell the name from a number.
    """
    if source is None:
        source = _vanilla_decomp_text_at_head('include/constants/chapters.h')
    labels = {}
    for name, value in re.findall(r'(CHAPTER_L_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', source):
        labels.setdefault(int(value, 0), name)
    return labels


def chapter_label_constant(slot, source=None):
    """The CHAPTER_L_* constant naming chapter slot `slot` (see chapter_label_constants)."""
    labels = chapter_label_constants(source)
    if slot not in labels:
        sys.exit('ERROR: no CHAPTER_L_* constant has value 0x%02X -- chapters.h does not name '
                 'chapter slot %d' % (slot, slot))
    return labels[slot]


def _vanilla_decomp_text_at_head(relative_path):
    """A decomp file as HEAD has it -- our injections are build artifacts, so the working
    tree is the wrong source for any question about what VANILLA says."""
    return subprocess.check_output(
        ['git', '-C', DECOMP, 'show', 'HEAD:' + relative_path], text=True)


def _assert_ms_symbol(symbol):
    if not symbol.startswith(MS_TABLE_PREFIX):
        sys.exit('ERROR: campaign-owned unit table %r must start with %r -- the prefix is '
                 'what distinguishes our data from the vanilla tables we no longer squat on'
                 % (symbol, MS_TABLE_PREFIX))


# The cleared gForceDeploymentList terminator (engine_hooks hook 6). Campaign injection inserts
# per-chapter force-deploy entries BEFORE it -- "any future per-chapter forced unit is added our
# way, not via the vanilla by-slot table" (engine_hooks docstring).
_FORCE_DEPLOY_TERMINATOR = '    {-1, 0, 0},\n}'


def _force_deployment_entries(pids, host_index):
    """Pure: the ForceDeploymentEnt rows force-deploying each `pid` in chapter slot `host_index`
    on ANY route (0xFF). This is vanilla's own data-driven force-deploy path (eventinfo.c's
    IsCharacterForceDeployed_ scans gForceDeploymentList by {pid, route, chapter}); our lord-
    select hook cleared vanilla's by-slot entries but KEPT the scan for exactly this. No new
    engine code -- a unit besides the chosen lead is fielded purely by adding a data row."""
    return ''.join('    {%s, 0xFF, %d}, /* MS force-deploy in chapter slot %d */\n'
                   % (pid, host_index, host_index) for pid in pids)


def _force_deploy_units(pids, host_index):
    """Insert `pids` into gForceDeploymentList (data_event_trigger.c) as force-deployed in
    chapter slot `host_index`. Additive (inserts before the cleared-list terminator), so
    multiple chapters can each force-deploy their own units. Runs AFTER _inject_lord_select_engine
    cleared the table (main() order). Idempotency: data_event_trigger.c is restored + re-cleared
    each build, so entries never accumulate across builds."""
    if not pids:
        return
    with open(engine_hooks.DATA_EVENT_TRIGGER_C, encoding='utf-8') as f:
        text = f.read()
    if text.count(_FORCE_DEPLOY_TERMINATOR) != 1:
        sys.exit('ERROR: gForceDeploymentList not in the expected cleared form (engine_hooks '
                 'hook 6) -- cannot add a per-chapter force-deploy entry')
    text = text.replace(_FORCE_DEPLOY_TERMINATOR,
                        _force_deployment_entries(pids, host_index) + _FORCE_DEPLOY_TERMINATOR, 1)
    with open(engine_hooks.DATA_EVENT_TRIGGER_C, 'w', encoding='utf-8') as f:
        f.write(text)


def _prepend_defeat_quote(quote):
    """Prepend an entry at the HEAD of gDefeatTalkList (battlequotes.c): the head entry
    wins GetDefeatTalkEntry's first-match scan, shadowing any vanilla entry for the
    same pid further down (the shadowing rule debriefed in inject_prologue step 5)."""
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n'
    if bq.count(head) != 1:
        sys.exit('ERROR: gDefeatTalkList head not in expected form in %s'
                 % BATTLEQUOTES_C)
    bq = bq.replace(head, head + quote + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)


def _write_chapter_title_card(host, title):
    """Compose the chapter's title-card banner (the intro/status banner is a 4bpp image, not
    text) and CONVERT it ourselves, rather than deleting the intermediates and trusting make.

    This used to delete `chap_title_N.4bpp{,.lz}` "so make re-converts". make does not: the
    incbin dependency reaches `data/data_chap_title.o` through `$$(data_dep)` -- a
    `$(shell scaninc ...)` target-specific variable resolved by `.SECONDEXPANSION` -- and GNU
    Make **3.81**, which is what Apple ships and what this repo builds with, drops it. Verified
    directly: with the .lz deleted, `make -n fireemblem8.gba` plans no rule that rebuilds it.

    That has two consequences and neither announces itself (this is #245's actual root cause,
    which was filed as a "TESTCH build race" -- it is not a race, and it is not TESTCH's):
      1. When `data_chap_title.o` DOES need reassembling, the build dies on
         `Error: file not found: graphics/chap_title/chap_title_N.4bpp.lz`.
      2. When it does NOT -- the common case, since its .s never changes -- the build succeeds
         and the ROM silently keeps the PREVIOUS card. A retitled chapter just never lands.

    So: run the same two gbagfx conversions the Makefile would have, then drop the .o so the
    new bytes are actually assembled in. Deterministic, and independent of the make version.
    """
    title_png = os.path.join(DECOMP, 'graphics', 'chap_title',
                             'chap_title_%d.png' % host['chapTitleId'])
    gen_chapter_title.compose_title(title).save(title_png)
    gbagfx = os.path.join(DECOMP, 'tools', 'gbagfx', 'gbagfx')
    if not os.path.exists(gbagfx):
        # A fresh checkout has no helper tools -- tools/setup-toolchain.sh omits upstream's
        # build_tools.sh (HANDOFF). Say so, rather than raising FileNotFoundError on a path.
        sys.exit('ERROR: %s is missing -- a fresh checkout needs the decomp helper tools:\n'
                 '  (cd fireemblem8u && ./build_tools.sh)' % gbagfx)
    four_bpp, lz = title_png[:-4] + '.4bpp', title_png[:-4] + '.4bpp.lz'
    for src, dst in ((title_png, four_bpp), (four_bpp, lz)):
        subprocess.run([gbagfx, src, dst], cwd=DECOMP, check=True)
    # The incbin dependency is dropped, so a fresh .lz alone would sit there unread.
    chap_title_o = os.path.join(DECOMP, 'data', 'data_chap_title.o')
    if os.path.exists(chap_title_o):
        os.remove(chap_title_o)


def inject_ch01(campaign, verbose=True):
    """Wire Ch1 "The Iron Trail" (#21) onto chapter slot 2 (ch00's MNC2(0x2) target).

    Field parity (decisions.md 2026-06-10): the deploy cap IS the ally UnitDefinition
    table -- GetChapterAllyUnitCount (eventscr3.c) counts its entries and the prep
    flow (SortPlayerUnitsForPrepScreen, prepscreen.c) clamps deployment to that
    count, force-deployed units first. The prep screen itself opens via the PREP
    event command (0x3E), reached through the shared CALL(EventScr_08591FD8)
    (eventscr.c:4283) exactly like every vanilla prep chapter (Ch4+). The
    hasPrepScreen field in chapter_settings.json is dead ("left over from FE7",
    chapterdata.h:37) -- the event call is the only gate.

    MUST run before inject_prologue: it copies vanilla slot 1's goal block (the
    Seize display template) which inject_prologue overwrites with the prologue's
    defeat_boss goal.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH01_CHAPTER_YAML)

    # 0. Beat 1 (#21): the Northlook opening, consumed from the chapter YAML's locked
    #    chapter_start `script:` and staged below (step 4) as a scenic off-map scene
    #    (BACG bg_Fireplace) at the head of EventScr_Ch2_BeginningScene. The script
    #    splits on `beat_break` sentinels into 5 messages (A-E); each rides one `Text()`
    #    whose trailing REMA clears all faces (eventscr.c sub_800E640) -> a fresh 4-face
    #    budget per beat. TWO SIDES: the quest-givers stand on the RIGHT (Hlin mid-right,
    #    Scramsax far-right, Hruna right) and the party on the LEFT. The roll-call rotates
    #    one PC at a time through the mid-left spotlight (eviction); monologue beats PRELOAD
    #    a few PCs as silent listeners on the left so Hlin/RBG address a populated room
    #    instead of empty air, and the haggle puts Hruna across from RBG. Hlin's final
    #    "who leads?" line stays in the scene (end of beat E, at the Northlook); the
    #    lord-select menu then plays over its own scenic BG (not the battle map).
    b1_card, b1_beats = _split_event_beats(chap, 'chapter_start', 'ch01 Beat 1',
                                           CH01_BEAT1_MSGS)

    b1_guests = {'hlin': _fid_tag(PROLOGUE_HLIN_SLOT),
                 'scramsax': _fid_tag(PROLOGUE_SCRAMSAX_SLOT),
                 'hruna': _fid_tag('VILLAGER_WOMAN')}
    b1_fid = _make_fid(b1_guests, 'ch01 Beat 1 unknown speaker')
    # Podium geometry (gTalkFaceHPosLut, scene.c, px = x*8; faces are 96px = 12 tiles):
    # FarLeft 24 | MidLeft 48 | Left 72 | Right 168 | MidRight 192 | FarRight 216.
    # Two faces only avoid overlap when >=96px apart, so the clean "two-shot" is
    # MidLeft <-> MidRight (144px). Speakers therefore default to the mid-left podium
    # and Hlin anchors mid-right; everyone rotating through one inner podium keeps the
    # stage to two non-overlapping faces (Nicolas, 2026-06-16: Hlin/Scramsax & the
    # 3-stack were too crowded). Silent listeners fill the OUTER podiums where a touch
    # of overlap reads as "a couple standing together."
    b1_home = {'hlin': '[OpenMidRight]'}
    # per-beat silent listeners (podium -> face), and per-beat speaker-podium overrides
    b1_preload = [
        [],                                                            # A: Scramsax<->Hlin two-shot
        [('[OpenMidRight]', b1_fid('hlin'))],                          # B: Hlin watches the roll-call
        [('[OpenLeft]', b1_fid('wolfram'))],                           # C: Wolfram listens (Braulo speaks here now)
        [],                                                            # D: Hruna<->Hlin two-shot
        [('[OpenMidRight]', b1_fid('hruna'))],                         # E: Hruna across from RBG
    ]
    # beat B: Pinky peeks out far-left beside his father (RBG speaks from mid-left) -- they
    # read as a pair (Nicolas, 2026-06-16: keep). Beat B now ENDS on that pair: Braulo's
    # "name the job" line moved to the head of beat C (YAML), so the beat's REMA clears the
    # RBG+Pinky pair before Braulo speaks. Otherwise Pinky lingered far-left BEHIND Braulo:
    # he sits on a different podium than the one Braulo's mid-left load would evict, so
    # nothing cleared him (Nicolas's friends, 2026-06-17). In beat C Braulo speaks from his
    # crowd spot (FarLeft) and stays as a silent listener through Hlin's story.
    b1_overrides = [None, {'pinky': '[OpenFarLeft]'},
                    {'braulo': '[OpenFarLeft]'}, None, None]

    # 0b. Ending "The Rolling Cheddar" (#21): the locked chapter_end `script:`, consumed
    #     the same way as Beat 1 -- a "Bryn Shander" location card + one message per beat
    #     (A-F), each rendered with the scenic full-screen wrap and staged below; each
    #     rides its own Text()/REMA in EventScr_Ch2_EndingScene (step 4) so the 4-face
    #     budget resets per beat. Duvessa (the host, Speaker of Bryn Shander) anchors the
    #     mid-right podium throughout; the party speaks from mid-left, with the other beat
    #     speaker(s) staged as clean two-shots opposite her (cf. Beat 1 podium geometry).
    end_card, end_beats = _split_event_beats(chap, 'chapter_end', 'ch01 ending',
                                             CH01_ENDING_MSGS)

    # narration = faceless stage-business box (no portrait); the fallback covers
    # the duvessa/hruna/baxby cutscene faces (GUEST_PORTRAIT_MAP).
    end_fid = _make_fid({'narration': None}, 'ch01 ending unknown speaker',
                        fallback=GUEST_PORTRAIT_MAP)
    # Duvessa hosts from mid-right (like Hlin in Beat 1); everyone else defaults mid-left.
    # Per-beat overrides put the OTHER speaker opposite her for a clean two-shot: Hruna
    # (C) and Meesmickle (D) take mid-right; in E, Baxby takes mid-right -- evicting
    # Duvessa's face there (a [ClearFace] step-out) as she gestures to the market and the
    # bird steps forward. Marty stays mid-left across E.
    end_home = {'duvessa': '[OpenMidRight]'}
    # NO silent-listener preloads: a preloaded face fades out and back in at every beat's
    # REMA boundary it straddles -- exactly the Marty/Duvessa "flashing during dialogue"
    # Nicolas flagged 2026-06-17. Each beat now shows ONLY its actual speakers, and the
    # scene is split so no character spans a REMA: consecutive same-speaker beats are
    # merged (A+B = one continuous Duvessa beat), and the REMA fades land only between
    # genuinely different casts (read as scene transitions, not flashes). In E2 the right
    # podium starts EMPTY so Baxby fades in fresh for his answer (Duvessa was cleared at
    # the E1->E2 boundary, never swapped on the same podium).
    end_preload = [[], [], [], [], [], [], []]
    # AB, C, D, E1, E2(narration -- faceless, override unused), E2b(Baxby fades in
    # mid-right opposite Marty), F.
    end_overrides = [None, {'hruna': '[OpenMidRight]'},
                     {'meesmickle': '[OpenMidRight]'}, None, None,
                     {'baxby': '[OpenMidRight]'}, None]

    # 1. Map: register the painted layout and point slot 2 at it + the winter tileset
    #    (same flow as inject_prologue step 1). Goal display = vanilla Ch1's own Seize
    #    template (windowDataType "seize"), copied from slot 1 while it is still vanilla.
    indices = _register_chapter_map(maps_dir, CH01_LAYOUT,
                                    'Manchego Stars ch01 layout (#21)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH01_HOST_INDEX, 1, 'seize',
        'ERROR: slot 1 goal is not the vanilla Seize template -- '
        'inject_ch01 must run BEFORE inject_prologue',
        indices, chap['chapter_number'], CH01_EVENT_GROUP,
        (CH01_GOAL_WINDOW_MSG, CH01_GOAL_STATUS_MSG))

    # 2. Rosters (events_udefs.c). Four tables, all reusing vanilla Ch2 symbols so no
    #    extern surgery is needed (scripts/eventinfo already declare them):
    #    - UnitDef_Event_Ch2Ally: the 4-slot deploy template = THE CAP. Never LOADed;
    #      the prep flow reads its entry count (cap) and positions (deploy tiles).
    #    - UnitDef_088B440C: the cast join-LOAD (whole roster enters the party at the
    #      Northlook; the engine benches everyone past the cap).
    #    - UnitDef_088B4344: the 7 initial goblins. UnitDef_088B44AC: the 3 west
    #      reinforcements (turn 3).
    # cast_names is parallel to cast: lord-select menu/confirm display names (#42).
    # available_at=1: the founding party on the field at ch01 -- later recruits (Baxby ch01
    # via market -> ch02 prep; Trex ch03) are not in the ch01 join-LOAD / lord-select / world map.
    cast, cast_names = _classed_cast(campaign, available_at=chap['chapter_number'])
    for unit_id, _, class_enum, _, _ in cast:
        if class_enum not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (unit %s)' % (class_enum, unit_id))
    if len(cast) > len(LORDSEL_CONFIRM_MSGS):
        sys.exit('ERROR: %d lord candidates > %d reserved confirm text ids'
                 % (len(cast), len(LORDSEL_CONFIRM_MSGS)))
    if len(cast) > len(CH01_JOIN_POSITIONS):
        sys.exit('ERROR: %d classed cast > %d ch01 join positions'
                 % (len(cast), len(CH01_JOIN_POSITIONS)))
    leader = 'CHARACTER_%s' % cast[0][1].upper()

    # classIndex rides the DEPLOY class (dce) -- which today equals the real vanilla class
    # (ce) for EVERY unit: the #65 clone-class approach is retired (custom anims ride the
    # per-character _u25 path; see deploy_class_for). The split survives only as a seam.
    join = [_ally_unit_entry(leader, slot, dce, lv, x, y,
                             ', '.join(CLASS_LOADOUT[ce]), ' /* %s */' % uid)
            for (uid, slot, ce, dce, lv), (x, y) in zip(cast, CH01_JOIN_POSITIONS)]
    deploy = _deploy_cap_entries(chap, cast, leader, 'ch01')

    by_eid = {e['id']: e for e in chap['enemy_units']}
    spear, axe = by_eid['goblin-spear'], by_eid['goblin-axe']
    chief, reinf = by_eid['goblin-chief'], by_eid['goblin-reinforcements']

    # Ch1's grunts are goblins on the map: swap their vanilla class for the cloned goblin
    # class (same stats/anim, goblin map sprite -- inject_enemy_class_reskins). Keyed by
    # the base class enum so only declared reskins apply; the chief (armor-knight) has no
    # reskin and stays the vanilla Knight sprite.
    reskin_by_base = {rk['base']: rk['slot'] for rk in enemy_class_reskins(campaign)}

    def grunt_class(cls_label):
        base = CH01_CLASS_IDS[cls_label]
        return reskin_by_base.get(base, base)

    enemies = []
    for x, y in spear['positions']:
        enemies.append(_enemy_unit_entry(
            '0x80', grunt_class(spear['class']), spear['level'], True, x, y,
            CH01_ITEM_IDS[spear['inventory'][0]['id']], CH01_AI[spear['ai_pattern']],
            ' /* goblin spear -- camp approach */'))
    for x, y in axe['positions']:
        enemies.append(_enemy_unit_entry(
            '0x80', grunt_class(axe['class']), axe['level'], True, x, y,
            CH01_ITEM_IDS[axe['inventory'][0]['id']], CH01_AI[axe['ai_pattern']],
            ' /* goblin raider -- mid-trail pursuer */'))
    cx, cy = chief['position']
    # The iron-ingots MacGuffin stays narrative (no FE8 item exists for it yet);
    # recovery is told in the ending scene. The chief mirrors Breguet 1:1: his slot's
    # vanilla boss bases, no autolevel, lv4, attack-in-place AI, ON the seize tile.
    enemies.append(_enemy_unit_entry(
        'CHARACTER_%s' % CH01_BOSS_SLOT, CH01_CLASS_IDS[chief['class']],
        chief['level'], False, cx, cy,
        CH01_ITEM_IDS[chief['inventory'][0]['id']], CH01_AI[chief['ai_pattern']],
        ' /* goblin chief -- boss, holds the seize tile */'))
    reinforce = []
    for cls, (x, y) in zip(reinf['composition'], reinf['positions']):
        reinforce.append(_enemy_unit_entry(
            '0x80', grunt_class(cls), reinf['level'], True, x, y,
            CH01_ITEM_IDS[reinf['inventory_by_class'][cls][0]],
            CH01_AI['reinforce'], ' /* west reinforcement, turn %d */'
            % reinf['spawn_turn']))

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    for marker, entries in (
            ('UnitDef_Event_Ch2Ally[] =', deploy),
            ('UnitDef_088B440C[] =', join),
            ('UnitDef_088B4344[] =', enemies),
            ('UnitDef_088B44AC[] =', reinforce)):
        block = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'
        udefs = _replace_brace_block(udefs, marker, block, EVENTS_UDEFS_C)
    # Lord-select candidate pids (#42), menu order = classed cast order; the engine
    # recovers the chosen pid by scanning permanent flags LORDSEL_FLAG_BASE + i
    # (LordSelect_GetPid, eventinfo.c).
    udefs += '\n'.join(
        ['', '/* Lord-select candidate pids (#42, build-generated): menu order =',
         '   classed cast order; chosen pid = flag scan (LordSelect_GetPid). */',
         'CONST_DATA u16 gLordSelectCandidates[] = {'] +
        ['    CHARACTER_%s, /* %s */' % (slot.upper(), uid)
         for uid, slot, _, _, _ in cast] +
        ['    0xFFFF,', '};', ''])
    # (The per-candidate pitch + "Choose your lead" header msg ids live in the eventscript
    #  TU as sLordSelectPitchMsg[] / an inlined header, drawn directly by LordSelect_DrawCard
    #  -- no global table is needed.)
    # Lord survivability floors (#45 3b): per-candidate { +maxHP, +Def, +Res }, PARALLEL to
    # gLordSelectCandidates above (same menu order). Computed @target 3.5 bulk-durability vs
    # Ch1 enemies -- the shamans' frail floor; the armor tanks score 0. The engine adds the
    # chosen lord's triple to its unit ONCE at chapter start, flag-gated (#45 3c).
    floor_rows = lord_floor_rows(campaign, [uid for uid, _, _, _, _ in cast])
    udefs += '\n'.join(
        ['', '/* Lord survivability floors (#45 3b, build-generated): per-candidate',
         '   { +maxHP, +Def, +Res } at base level, parallel to gLordSelectCandidates above.',
         "   The engine adds the chosen lord's triple to maxHP/curHP/def/res ONCE at chapter",
         '   start, gated by a permanent flag (#45 3c) -- bakes in, then fades as it levels. */',
         'CONST_DATA s8 gLordFloorDeltas[] = {'] +
        ['    %d, %d, %d, /* %s */' % (hp, df, res, uid)
         for uid, hp, df, res in floor_rows] +
        ['};', ''])
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Event lists (ch2-eventinfo.h). Turn: the west wave on turn 3 (vanilla's own
    #    reinforcement idiom: FACTION_ID_BLUE = appear at the start of the player
    #    phase, act on the following enemy phase -- cf. ch9a). Location: the two
    #    vanilla-Ch1-parity hint houses + Seize on the chief's tile (the Seize macro
    #    raises EVFLAG_WIN -> ending scene). Turn: the road-sign+body narration at
    #    battle start (turn 1, #5) + Izobai's taunt + reinforcements. Misc:
    #    CauseGameOverIfLordDies (fires on EVFLAG_GAMEOVER, raised by the UnitKill
    #    hook when the chosen lead falls -- _inject_lord_select_engine, #42).
    sx, sy = chap['objective']['seize_tile']
    houses = [e for e in chap['events'] if e.get('type') == 'house']
    # The road-sign + body narration (#5): fires at BATTLE START as a turn-1 event (not a
    # tile step), so the party always reads it. Presence-checked here; wired as the first
    # turn-1 TURN entry below (its script body is EventScr_Ch2_Talk_EirikaRoss, step 4).
    next(e for e in chap['events'] if e.get('trigger') == 'battle_start')
    with open(CH2_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    info = _replace_brace_block(
        info, 'EventListScr_Ch2_Turn[] =',
        '{\n    TURN(0x0, EventScr_Ch2_Talk_EirikaRoss, 1, 0, FACTION_ID_BLUE)'
        ' /* #5: roadsign + body, read at battle start (was a [8,8] tile trigger) */\n'
        '    TURN(0x0, EventScr_Ch2_Turn2Player, 1, 0, FACTION_ID_BLUE)'
        ' /* Izobai turn-1 taunt */\n'
        '    TURN(0x0, EventScr_Ch2_Turn1Player, %d, 0, FACTION_ID_BLUE)'
        ' /* west reinforcements */\n'
        '    END_MAIN\n}' % reinf['spawn_turn'], CH2_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch2_Character[] =', '{\n    END_MAIN\n}', CH2_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch2_Location[] =',
        '{\n    House(0x0, EventScr_Ch2_Village1, %d, %d)\n'
        '    House(0x0, EventScr_Ch2_Village2, %d, %d)\n'
        '    Seize(%d, %d)\n    END_MAIN\n}'
        % (houses[0]['tile'][0], houses[0]['tile'][1],
           houses[1]['tile'][0], houses[1]['tile'][1], sx, sy), CH2_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch2_Misc[] =',
        '{\n    CauseGameOverIfLordDies\n    END_MAIN\n}',
        CH2_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch2_Tutorial[] =', '{\n    NULL\n}', CH2_EVENTINFO_H)
    with open(CH2_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # 4. Scenes (ch2-eventscript.h), mechanical pass -- real dialogue lands in the
    #    dialogue pass (LAST, per the slice plan). Beginning = vanilla prep-chapter
    #    shape (cf. Ch4): the ch00 guests leave the party (DISA = ClearUnit -- Orson's
    #    own departure idiom), enemies deploy, the cast joins, then the shared prep
    #    call. PREP hides all units, runs Pick Units (cap 4), and redeploys the picks
    #    onto the ally-template tiles.
    # 4a. Lord-select menu (#42), prepended so the scene below can ASMC it. Pure
    #     route-split clone: same draw callback, same menu flow, same confirm idiom
    #     (Command stores the confirm text id in EVT_SLOT_C; the scene SADDs it
    #     into slot 2, TEXTSHOW(0xffff) shows it, and the [Yes] answer comes back
    #     in EVT_SLOT_C -- 1 = yes, anything else re-opens the menu).
    items = []
    for i, ((uid, slot, _, _, _), name) in enumerate(zip(cast, cast_names)):
        items.append(
            '    {\n'
            '        .name = (const char *)0x8205958, /* vanilla dummy (rodata is discarded) */\n'
            '        .nameMsgId = 0x%X, /* %s rides this vanilla name slot */\n'
            '        .overrideId = %d,\n'
            '        .color = TEXT_COLOR_SYSTEM_WHITE,\n'
            '        .isAvailable = MenuAlwaysEnabled,\n'
            '        .onDraw = MenuCommand_DrawRouteSplit,\n'
            '        .onSelected = Command_SelectLord,\n'
            '        .onSwitchIn = LordSelect_DrawCard, /* #46: live candidate card */\n'
            '    },' % (vanilla_name_text_id(slot), uid, i))
    menu_code = (
        '/* ==== Lord select (#42/#46, build-generated): "choose your lead" screen ====\n'
        '   A stock candidate menu (route-split flow: pick -> confirm text in EVT_SLOT_C)\n'
        '   COMPOSED with a live info card (Nicolas 2026-06-25 layout, supersedes the\n'
        '   prep_unitselect clone). The names list rides the LEFT column; as the cursor\n'
        '   lands on candidate i the menu engine fires onSwitchIn (uimenu.c), which draws\n'
        '   that candidate\'s FULL 80x72 bust on the RIGHT (PutFace80x72 -> BG tilemap, so\n'
        '   it layers over the scenic BACG with no OBJ-vs-BG priority fight) + the\n'
        '   qualitative PITCH (#46) below it, in DrawUiFrame panels. The pick is stored as\n'
        '   permanent flag 0x%X + item index and read back by LordSelect_GetPid\n'
        '   (eventinfo.c). One confirm + one pitch text per candidate (dead vanilla\n'
        '   Ch1-tutorial slot-2 message ids). Coords are render-tunable. */\n'
        '\n'
        '#include "uimenu.h"\n'
        '#include "hardware.h"\n'
        '#include "uiutils.h"\n'
        '#include "bmlib.h"\n'
        '#include "bmunit.h"\n'
        '#include "face.h"\n'
        '#include "fontgrp.h"\n'
        '\n'
        'extern const u16 gLordSelectCandidates[]; /* events_udefs.c */\n'
        '\n'
        'static CONST_DATA u16 sLordSelectConfirmMsg[] = { %s };\n'
        '/* #46: qualitative blurb per candidate, PARALLEL to gLordSelectCandidates. */\n'
        'static CONST_DATA u16 sLordSelectPitchMsg[] = { %s };\n'
        '\n'
        '/* #46 card (Nicolas 2026-06-25 layout): names MENU on the LEFT; as the cursor\n'
        '   lands on candidate i, draw their FULL 80x72 bust on the RIGHT (PutFace80x72 ->\n'
        '   BG tilemap, over the scenic BACG) + the qualitative PITCH wrapped BELOW it.\n'
        '   The 8-item menu exhausts the shared system-font tile pool (each glyph is 2\n'
        '   tiles tall), so the pitch gets its OWN font in free BG VRAM (tile 0x140 =\n'
        '   VRAM 0x2800 (0x140<<5), in the gap between the menu pool -- which spills just\n'
        '   past the system font at 0x80 -- and the bust at 0x200) -- no clash with the\n'
        '   menu name tiles, full manual control of the box. */\n'
        'extern void InitTextFont(struct Font * font, void * vram, int chr, int palid);\n'
        '\n'
        'int LordSelect_DrawCard(struct MenuProc* menu, struct MenuItemProc* menu_item)\n'
        '{\n'
        '    const struct CharacterData* cd =\n'
        '        GetCharacterData(gLordSelectCandidates[menu_item->itemNumber]);\n'
        '    const char* s = GetStringFromIndex(sLordSelectPitchMsg[menu_item->itemNumber]);\n'
        '    struct Font pitchFont;\n'
        '    char buf[40];\n'
        '    char* o = buf;\n'
        '    int line = 0;\n'
        '\n'
        '    /* full bust, RIGHT, top-aligned at row 4 (rows 4..0xC): on a 20-row screen\n'
        '       under a 4-row title, this is the only fit that leaves 3 pitch lines\n'
        '       (rows 0xD/0xF/0x11) clear of the box bottom border at row 0x13. Clear the\n'
        '       BG0 block first (reveals the blue panel on BG1), then redraw. */\n'
        '    TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 0xE, 4), 15, 9, 0);\n'
        '    PutFace80x72(menu, TILEMAP_LOCATED(gBG0TilemapBuffer, 0x11, 4),\n'
        '                 cd->portraitId, 0x200, 0xD);\n'
        '\n'
        '    /* pitch BELOW the bust, in its OWN font/VRAM (tile 0x140), so it never\n'
        '       collides with the menu name tiles. [LF]-delimited lines, two tile-rows\n'
        '       apart (FE8 text is 16px tall); control bytes (the [.] parity pad) skipped.\n'
        '       Restore the system font afterwards so the menu keeps drawing. */\n'
        '    InitTextFont(&pitchFont, (void*)(0x06000000 + 0x2800), 0x140, 0);\n'
        '    /* Scrub the WHOLE pitch tile band (3 lines x 15 cols x 2 rows = 90 tiles)\n'
        '       before drawing: a shorter line over a previous candidate\'s longer one left\n'
        '       its tail glyphs in VRAM (per-line ClearText alone did not catch it). */\n'
        '    CpuFastFill16(0, (void*)(0x06000000 + 0x2800), 90 * 0x20);\n'
        '    TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 0xE, 0xD), 15, 6, 0);\n'
        '    for (;; s++) {\n'
        '        if (*s == 0x01 || *s == 0x00) {\n'
        '            *o = 0;\n'
        '            /* PutDrawText(NULL,...) InitTexts a throwaway Text from the ACTIVE\n'
        '               font (pitchFont) -- so the line\'s tiles allocate fresh from tile\n'
        '               0x140, chr_counter advancing per line so lines do not overlap. */\n'
        '            if (line < 3 && o != buf)\n'
        '                PutDrawText((struct Text*)0,\n'
        '                            TILEMAP_LOCATED(gBG0TilemapBuffer, 0xE, 0xD + 2 * line),\n'
        '                            TEXT_COLOR_SYSTEM_WHITE, 0, 15, buf);\n'
        '            if (*s == 0x00)\n'
        '                break;\n'
        '            line++;\n'
        '            o = buf;\n'
        '        } else if ((u8)*s >= 0x20 && o < buf + sizeof(buf) - 1) {\n'
        '            *o++ = *s; /* bounded: a pathologically long unwrapped line truncates,\n'
        '                          never smashes the stack (lines wrap at 20, buf is 40) */\n'
        '        }\n'
        '    }\n'
        '    SetTextFont(0); /* restore the system font for the menu */\n'
        '    InitSystemTextFont();\n'
        '\n'
        '    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);\n'
        '    return 0;\n'
        '}\n'
        '\n'
        'u8 Command_SelectLord(struct MenuProc* menu, struct MenuItemProc* menu_item)\n'
        '{\n'
        '    int i;\n'
        '\n'
        '    /* re-picks (confirm answered "No") must not leave a stale flag */\n'
        '    for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '        ClearFlag(0x%X + i);\n'
        '    }\n'
        '\n'
        '    SetFlag(0x%X + menu_item->itemNumber);\n'
        '    SetEventSlotC(sLordSelectConfirmMsg[menu_item->itemNumber]);\n'
        '\n'
        '    return MENU_ACT_CLEAR | MENU_ACT_SND6A | MENU_ACT_END | MENU_ACT_SKIPCURSOR;\n'
        '}\n'
        '\n'
        'CONST_DATA struct MenuItemDef MenuItemDef_LordSelect[] = {\n'
        '%s\n'
        '    { 0 }\n'
        '};\n'
        '\n'
        'CONST_DATA struct MenuDef MenuDef_LordSelect = {\n'
        '    .rect = {1, 0, 9, 0}, /* names MENU on the LEFT (left-to-right reading) */\n'
        '    .style = 1,\n'
        '    .menuItems = MenuItemDef_LordSelect,\n'
        '};\n'
        '\n'
        'void CallLordSelectMenu(ProcPtr proc)\n'
        '{\n'
        '    ClearBg0Bg1();\n'
        '    /* BG2 OFF: the menu plays over a scenic BACG on BG3 (#21), not the battle\n'
        '       map -- leaving BG2 enabled would show the (disabled) map layer behind. */\n'
        '    SetDispEnable(1, 1, 0, 1, 1);\n'
        '    SetTextFont(0);\n'
        '    InitSystemTextFont();\n'
        '    LoadUiFrameGraphics();\n'
        '\n'
        '    /* title across the TOP: opaque frame box on the menu back BG (BG1, where the\n'
        '       UI-frame gfx is loaded), text on the front BG (BG0). */\n'
        '    DrawUiFrame(gBG1TilemapBuffer, 0xA, 0, 0x13, 4, 0, 1);\n'
        '    PutStringCentered(TILEMAP_LOCATED(gBG0TilemapBuffer, 0xB, 1),\n'
        '                      TEXT_COLOR_SYSTEM_WHITE, 0xE, GetStringFromIndex(0x%X));\n'
        '\n'
        '    /* opaque panel backing the BUST + pitch (BG1). Right edge (0xD+0x10=0x1D)\n'
        '       lines up with the title box right edge (0xA+0x13=0x1D), per Nicolas. Tall\n'
        '       enough (rows 4..0x14) for the 9-row bust AND 3 pitch lines below it. */\n'
        '    DrawUiFrame(gBG1TilemapBuffer, 0xD, 4, 0x10, 0x10, 0, 1);\n'
        '\n'
        '    /* (blurb text handles are InitText\'d in LordSelect_DrawCard, parked above\n'
        '       the menu names that StartMenu allocates below.) */\n'
        '    StartMenu(&MenuDef_LordSelect, proc);\n'
        '}\n'
        '\n'
        % (LORDSEL_FLAG_BASE,
           ', '.join('0x%X' % m for m in LORDSEL_CONFIRM_MSGS[:len(cast)]),
           ', '.join('0x%X' % m for m in LORDSEL_PITCH_MSGS[:len(cast)]),
           LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE, '\n'.join(items),
           LORDSEL_HEADER_MSG))
    with open(CH2_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    script = menu_code + script
    # Declare CallLordSelectMenu in eventcall.h so eventscript files included BEFORE
    # ch2-eventscript.h (e.g. the ch1 sandbox, debug fast-boot) can ASMC it.
    eventcall_h = os.path.join(DECOMP, 'include', 'eventcall.h')
    with open(eventcall_h, encoding='utf-8') as f:
        ec = f.read()
    anchor = 'void CallRouteSplitMenu(ProcPtr proc);\n'
    if anchor in ec and 'CallLordSelectMenu' not in ec:
        ec = ec.replace(
            anchor, anchor + 'void CallLordSelectMenu(ProcPtr proc); /* lord select (#46) */\n', 1)
        with open(eventcall_h, 'w', encoding='utf-8') as f:
            f.write(ec)
    beat1_labels = ['A -- Hlin & Scramsax in from the cold',
                    'B -- the roll-call (PCs one at a time + RBG/Pinky, Hlin watching)',
                    "C -- Hlin's story: the endless winter",
                    "D -- the test: Hruna's iron job",
                    'E -- the price; Braulo commits; Hlin asks who leads']
    beat1_text_calls = _scenic_beat_calls(CH01_BEAT1_MSGS, b1_beats, beat1_labels)
    beat1_scene = (
        '    /* Beat 1 (#21): the Northlook -- scenic off-map scene over bg_Fireplace.\n'
        '       Built from the chapter YAML; faces are budget-managed (the 4-slot fix\n'
        '       in _script_to_message) and staged as clean two-shots (speakers rotate\n'
        '       through the mid-left/mid-right inner podiums; silent listeners fill the\n'
        '       outer ones so no one talks to an empty room). The brown-box card\n'
        '       auto-dismisses (blocks ~100 frames then fades). Beat E ends on Hlin\'s\n'
        '       "who leads?" -- still at the Northlook. */\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(BG_FIREPLACE)\n'
        '    FADU(16) /* chapter loads come up black; reveal the tavern BG */\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "The Northlook" location card */\n'
        % CH01_BEAT1_CARD_MSG
        + beat1_text_calls +
        '    FADI(16) /* fade the Northlook out */\n')
    script = _replace_brace_block(
        script, 'EventScr_Ch2_BeginningScene[] =',
        '{\n'
        + beat1_scene +
        '    /* Lord select (#42) on its OWN scenic BG -- a "choose your leader" screen,\n'
        '       NOT the battle map (Nicolas, 2026-06-16). The menu window draws on BG0/1\n'
        '       over the BACG on BG3; CallLordSelectMenu keeps BG2 (map) off. The explainer\n'
        '       + re-pick loop is the SHARED _lord_select_event_seq (also the lord-fast\n'
        '       debug boot); here we append the post-Yes map build. */\n'
        + _lord_select_event_seq(CH01_LORDSEL_BG, LORDSEL_EXPLAINER_MSG)
        + '    EVBIT_MODIFY(0x0)\n'
        '    /* leader chosen: fade the scenic BG out, build the battle map, deploy. */\n'
        '    FADI(16)\n'
        '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
        '    LOMA(0x%X) /* RestartBattleMap -- builds the trail map fresh (cf. ch13a) */\n'
        '    DISA(CHARACTER_NATASHA) /* Hlin stays in Bryn Shander (ch00 guest) */\n'
        '    DISA(CHARACTER_KYLE)    /* Scramsax departs (ch00 guest) */\n'
        '    LOAD1(0x1, UnitDef_088B4344) /* goblins */\n'
        '    ENUN\n'
        '    LOAD1(0x1, UnitDef_088B440C) /* the company signs on at the Northlook */\n'
        '    ENUN\n'
        # NO FADU here: the shared prep prologue (EventScr_08591F64) fades to black itself before
        # drawing Preparations, so revealing the freshly-LOMA'd map first only FLASHES it for a
        # beat before prep blanks it. Vanilla prep chapters go straight into CALL(prep). Stay black.
        '    CALL(EventScr_08591FD8) /* preparations (PREP, event cmd 0x3E) */\n'
        '    ENUT(8)\n'
        '    EVBIT_T(7)\n'
        '    ENDA\n}' % (CH01_HOST_INDEX,),
        CH2_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Turn1Player[] =',
        '{\n    SVAL(EVT_SLOT_2, UnitDef_088B44AC)\n'
        '    CALL(EventScr_LoadReinforce)\n'
        '    EVBIT_T(7)\n    ENDA\n}', CH2_EVENTSCRIPT_H)
    # Izobai's turn-1 taunt rides the spare vanilla Turn2Player slot (externed in
    # eventcall.h; fired at turn 1 by the Turn list above), shown over the map.
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Turn2Player[] =',
        '{\n    TEXTSHOW(0x%X) /* Izobai turn-1 taunt */\n    TEXTEND\n    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}' % CH01_TAUNT_MSG, CH2_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Village1[] =',
        '{\n    IGNORE_KEYS(0)\n    HouseEvent(0x93B, 0x0)\n}', CH2_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Village2[] =',
        '{\n    IGNORE_KEYS(0)\n    HouseEvent(0x93C, 0x0)\n}', CH2_EVENTSCRIPT_H)
    # The trailhead sign + the body are faceless narration shown OVER the battle map at
    # BATTLE START (wired as the first turn-1 TURN entry above, #5 Nicolas 2026-06-17 --
    # was a [8,8] tile trigger; now the party always reads it). SOLOTEXTBOXSTART renders
    # them in an opaque, bordered box (gProcScr_BoxDialogue, helpbox.c) instead of the
    # default translucent map talk window -- readable over the snow ("roadsign hard to
    # read"). EVT_SLOT_B = 0x00FF00FF feeds x=y=0xFF into sub_800E31C, so the box
    # auto-centers (dialogue-box config flag 0x100). One SOLOTEXTBOXSTART per page since
    # REMA tears the talk down between them.
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Talk_EirikaRoss[] =',
        '{\n    SVAL(EVT_SLOT_B, 0xFF00FF) /* x=y=0xFF -> auto-center the solo box */\n'
        '    SOLOTEXTBOXSTART\n'
        '    TEXTSHOW(0x955) /* road sign + gouged warning */\n    TEXTEND\n    REMA\n'
        '    SOLOTEXTBOXSTART\n'
        '    TEXTSHOW(0x%X) /* the smashed sled + the body, just past the sign */\n'
        '    TEXTEND\n    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}' % CH01_BODY_MSG, CH2_EVENTSCRIPT_H)
    # ch01 ending "The Rolling Cheddar" (#21): scenic in-town scene, same machinery as
    # Beat 1's BeginningScene -- a "Bryn Shander" brown-box card + one Text() per beat
    # (A-F), each Text()'s trailing REMA clearing faces (fresh 4-face budget). The locked
    # bodies + staging are built in step 0b/step 6. The scene plays over BG_MS_BRYN_SHANDER_WINTER,
    # a vendored winter CG (#21). The 2026-06-17 call to keep vanilla's green BG_NORMAL_VILLAGE was
    # about PALETTE-swapping it, which just washed it out; the vendored-BG pipeline built for ch02
    # (bg_to_fe8.py -> inject_backgrounds) makes a real snowbound town available instead.
    # The ending MNC2s into ch02 "Cold Welcome" (hosted on chapter slot 3 by
    # inject_ch02; see the generated EventScr_Ch2_EndingScene below). Before ch02 landed
    # it parked on the dev placeholder instead.
    end_text_calls = _scenic_beat_calls(
        CH01_ENDING_MSGS, end_beats,
        ['A+B -- Duvessa thanks them, commissions them, grants the sled, points west',
         'C -- Wolfram asks Hruna for the iron to armor the sled',
         'D -- RBG over-engineers it; names it the Rolling Cheddar',
         'E1 -- Duvessa points to the axe-beak at the market',
         'E2 -- "Marty leans in..." faceless narration (opaque solo box, #58)',
         'E2b -- Marty wins over Baxby the axe-beak (first recruit)',
         'F -- "Targos is expecting weather. Better hurry."'])
    script = _replace_brace_block(
        script, 'EventScr_Ch2_EndingScene[] =',
        '{\n    MUSC(SONG_VICTORY)\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(BG_MS_BRYN_SHANDER_WINTER) /* Bryn Shander -- vendored winter CG (#21) */\n'
        '    FADU(16) /* chapter ending comes up black; reveal the town BG */\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "Bryn Shander" location card */\n'
        % CH01_ENDING_CARD_MSG
        + end_text_calls +
        '    FADI(16) /* fade the town out */\n'
        '    MNC2(0x%X) /* -> ch02 "Cold Welcome", hosted on chapter slot 3 (inject_ch02) */\n'
        '    ENDA\n}' % CH02_HOST_INDEX,
        CH2_EVENTSCRIPT_H)
    with open(CH2_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 5. The chief's defeat quote: head of gDefeatTalkList (same shadowing rule as the
    #    prologue entries). No flag -- the win is the Seize, not the boss kill.
    quote = ('    {\n'
             '        .pid     = CHARACTER_%s, /* goblin chief death quote (ch01) */\n'
             '        .route   = CHAPTER_MODE_ANY,\n'
             '        .chapter = CHAPTER_L_2, /* ch01 is hosted on chapter slot 2 */\n'
             '        .msg     = 0x0961, /* body rewritten from the chapter YAML */\n'
             '    },' % CH01_BOSS_SLOT)
    _prepend_defeat_quote(quote)

    # 6. Texts. Overwritten ids are vanilla slot-2 messages our build can never show
    #    (the vanilla Ch2 scenes are gone) plus vanilla Ch1's own house hints, which
    #    only the Ch1 location list referenced -- and our prologue host stripped it.
    #    House/sign/ending bodies are functional placeholders for the playtests; the
    #    dialogue pass owns the real words.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, vanilla_name_text_id(CH01_BOSS_SLOT),
                     name_message_body(display_name(chief)))
    set_message_body(lines, host['chapTitleTextId'],
                     name_message_body(chap['title']))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Seize camp'))
    set_message_body(lines, host['goal']['windowTextId'],
                     goal_window_body('Seize camp'))
    chief.setdefault('id', 'goblin-chief')
    # Izobai (boss, her custom bust on the Breguet slot): turn-1 taunt + death quote,
    # both from the chapter YAML (lore/izobai.md voice). She/her throughout.
    izobai_face = {'izobai': ('[OpenMidRight]', _fid_tag(CH01_BOSS_SLOT))}
    set_message_body(lines, CH01_TAUNT_MSG, _script_to_message(
        [{'izobai': chief['taunt']}], izobai_face))
    set_message_body(lines, 0x961, _script_to_message(
        [{'izobai': chief['death_quote']}], izobai_face))
    # Hint houses -- vanilla Ch1's own two house quotes (0x93B/0x93C) reskinned with the
    # goblin nouns (dialogue pass, 2026-06-17). Two different villager faces, like vanilla.
    set_message_body(lines, 0x93B, _script_to_message([{'villager': (
        "The rumors are true, aren't they? Goblins have taken the old waystation. "
        "Looks like they've dug into the mounds, too. Smart work -- the mounds provide "
        "defense and heal wounds to boot. They must be vicious, to have taken it. "
        'Watch yourself.'
    )}], {'villager': ('[OpenMidLeft]', '[FID_VillagerMan3]')}))
    set_message_body(lines, 0x93C, _script_to_message([{'villager': (
        'That goblin warlord, Izobai, was wearing the finest scrap-plate I have seen. '
        'It looked like it could turn aside almost any blade you swing at it. I know '
        "my armor, though. I'll wager a good blast of magic could get right through it."
    )}], {'villager': ('[OpenMidLeft]', '[FID_VillagerMan4]')}))
    # Trailhead (msg 0x955) = the sign + gouged warning; the body (CH01_BODY_MSG) follows
    # in the same trigger -- faceless narration, hand-wrapped at the on-map width.
    set_message_body(lines, 0x955, _term_pad(
                     'BRYN SHANDER -- 2 MILES.[LF]\nBelow it, freshly gouged:[A][LF]\n'
                     '-- KEEP WALKING --[X]'))
    set_message_body(lines, CH01_BODY_MSG, _term_pad(
                     'Just past the sign, a sled[LF]\nlies smashed in the snow.[A][LF]\n'
                     'Its driver lies beside it --[LF]\na dwarf, in pieces.[A][LF]\n'
                     'The iron is gone. Goblin[LF]\ntracks lead up the trail.[X]'))
    # ch01 ending "The Rolling Cheddar" (#21): the locked chapter_end script -> a "Bryn
    # Shander" card + one message per beat (A-F), rendered at the scenic full-screen wrap
    # with the staging built in step 0b (Duvessa hosts mid-right; two-shots opposite).
    # Each beat rides its own Text()/REMA (step 4), so the 4-face budget resets per beat.
    # (0x954, the old placeholder "ingots recovered" body, is repurposed as the dev
    # placeholder line -- DEV_PLACEHOLDER_MSG; the ingot recovery is told in beat A.)
    set_message_body(lines, DEV_PLACEHOLDER_MSG, dev_placeholder_message())
    set_message_body(lines, CH01_ENDING_CARD_MSG, name_message_body(end_card))
    _emit_scene_beats(lines, CH01_ENDING_MSGS, end_beats, end_fid, end_home,
                      end_overrides, end_preload)
    # Beat 1 (#21): the Northlook opening. Card + one message per beat (A-E), rendered
    # from the chapter YAML's locked script with the scenic full-screen wrap width and
    # the per-beat two-sided staging + silent listeners built in step 0. Each beat rides
    # its own Text()/REMA, so the 4-face budget resets per beat.
    set_message_body(lines, CH01_BEAT1_CARD_MSG, name_message_body(b1_card))
    _emit_scene_beats(lines, CH01_BEAT1_MSGS, b1_beats, b1_fid, b1_home,
                      b1_overrides, b1_preload, width=42)
    # Lord select (#42): Hlin's "who leads?" already lands in beat E (at the Northlook),
    # so the menu opens directly over its scenic BG -- no separate prompt. Per-candidate
    # confirm texts keep the vanilla route-split shape (cf. MSG_C14/C17/C18) incl. the
    # odd-printable-count [.] parity pad.
    for i, name in enumerate(cast_names):
        q = 'Will %s lead the party?' % name
        set_message_body(lines, LORDSEL_CONFIRM_MSGS[i], '%s%s[LF]\n[Yes][X]'
                         % (q, '[.]' if len(q) % 2 else ''))
    # Lord-select candidate pitches (#46): drawn IN-MENU by LordSelect_DrawCard, which
    # splits the decoded body on [LF] and renders each line through its own dedicated font
    # (no [A] paging -- the pitch is one static 3-line panel below the bust). _term_pad
    # guards the terminator parity (final-run rule). Build hard-fails on a missing pitch
    # (lord_select_pitches).
    for i, (uid, pitch) in enumerate(lord_select_pitches(campaign,
                                                         [u for u, *_ in cast])):
        body = '[LF]'.join(_wrap_fe_lines(_fe_dialogue_text(pitch), width=20))
        set_message_body(lines, LORDSEL_PITCH_MSGS[i], _term_pad(body + '[X]'))
    # The one-time explainer box (#46 (a)) rides the normal tutorial text box, so it uses
    # the talk decoder: [A] page breaks every two lines + the standard [.] parity pad.
    expl = _wrap_fe_lines(_fe_dialogue_text(LORDSEL_EXPLAINER_TEXT), width=29)
    expl_body = ''.join(
        ln + ('' if j == len(expl) - 1
              else '[A]' if (j + 1) % 2 == 0 else '[LF]')
        for j, ln in enumerate(expl))
    set_message_body(lines, LORDSEL_EXPLAINER_MSG, _term_pad(expl_body + '[X]'))
    # Lord-select screen title (#46): "Choose your lead", drawn by the generated
    # CallLordSelectMenu title box (the prep screen's own "Pick N Units Left" is untouched).
    set_message_body(lines, LORDSEL_HEADER_MSG, _term_pad('Choose your lead[X]'))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 6a. Title card image (the intro/status banner is a 4bpp image, not text).
    _write_chapter_title_card(host, 'Ch.1: ' + chap['title'])

    if verbose:
        print('  ch01 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'deploy cap %d + PREP (vanilla Ch4+ idiom)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH01_HOST_INDEX, len(deploy)))
        print('  rosters: %d cast join, %d goblins + chief on (%d,%d) [Seize], '
              '%d west reinforcements turn %d'
              % (len(cast), len(enemies) - 1, cx, cy, len(reinforce),
                 reinf['spawn_turn']))


# Campaign event BGs, in slot order. Each rides a NEW gConvoBackgroundData index; the 240x160
# source PNG (tools/bg_to_fe8.py output, <=8 banks) lives in campaigns/<c>/backgrounds/<stem>.png
# and make's generic bg rules build its bins. The vanilla enum ENDS at BG_RANDOM (0x37, a
# sentinel with no real BG). Rather than shove BG_RANDOM aside for each new BG (a per-BG hack
# that caps at one), we APPEND campaign BGs PAST it starting at 0x38 -- the same "append into
# free enum space, never disturb a vanilla slot" model as the appended enemy/class slots (0x80+)
# -- so the range grows without limit. The two pre-0x38 gaps (0x36 free + 0x37 BG_RANDOM) get
# harmless placeholder table rows so the table stays index==enum contiguous. (enum_name, stem, credit).
CAMPAIGN_BG_SLOT0 = 0x38   # first campaign BG index -- PAST the vanilla BG_RANDOM sentinel (0x37)
CAMPAIGN_BGS = [
    ('BG_MS_TARGOS_WINTER',   'bg_TargosWinter',   '{Zeldacrafter}'),  # ch02 ending: Targos at night
    ('BG_MS_TERMALAINE_MINE', 'bg_TermalaineMine', '{FE7 rip}'),        # ch03 opening: the mine mouth
    # ch04 opening beat B: the fogged forest edge. NOT a vendored import and not new tile art --
    # vanilla's own bg_Plain_1 TILES under a winter palette. The BG "fog" variants (_Fog, _Sunset,
    # _Night) are palette swaps of one image, which is why BG_PLAIN_1_FOG is a green summer meadow
    # under white haze and read wrong in a snowbound chapter. Additive slot, so vanilla's BG is
    # untouched and still available. Approved by Nicolas 2026-07-31 over BG_TREES.
    ('BG_MS_LONELYWOOD_FOG',  'bg_LonelywoodFog',  '{vanilla FE8 bg_Plain_1, winter palette}'),
    # The two Ten-Towns settlements that had been borrowing another town's backdrop. Both are
    # Fenriel winter CGs, already 240x160, and both need the 8-bank refit in bg_to_fe8.py (a
    # dithered CG has tiles of 16-18 colours, so the greedy single-set pack cannot hold them).
    # Distinct backdrops per town is the point: BG_MS_TARGOS_WINTER already backs ch02's and
    # ch03's endings, and a third reuse reads as one town (Nicolas, 2026-08-09).
    ('BG_MS_BRYN_SHANDER_WINTER', 'bg_BrynShanderWinter', '{Fenriel}'),  # ch01 ending: walled town at dusk
    ('BG_MS_BREMEN_WINTER',       'bg_BremenWinter',      '{Fenriel}'),  # ch07 (#27): the lakeside town
]


def inject_backgrounds(campaign, verbose=True):
    """Append the campaign's vendored event BGs as NEW gConvoBackgroundData slots (#22).

    Additive: each BG gets a fresh enum id (backgrounds.h), a table row (eventscr2.c) and
    incbin symbols (data_bg.s) -- never an edit to a vanilla entry. PNGs come from
    campaigns/<c>/backgrounds/ (tools/bg_to_fe8.py output); the decomp's generic
    gbagfx/FETSATOOL rules build .feimg2.bin.lz / .fetsa2.bin / .gbapal at make time. The
    four patched decomp files are in PATCHED_DECOMP_FILES (restored from HEAD each build),
    so insert-before-anchor stays idempotent; the copied PNG + its stale bins are refreshed."""
    src_dir = os.path.join(REPO, 'campaigns', campaign, 'backgrounds')
    # slot(i) = CAMPAIGN_BG_SLOT0 + i, all PAST the BG_RANDOM sentinel (0x37). Assets (PNG copy,
    # incbin syms, externs) are per-BG; the enum + table build handles the sentinel gap below.
    by_slot, data_syms, externs = {}, [], []
    for i, (enum_name, stem, _credit) in enumerate(CAMPAIGN_BGS):
        slot = CAMPAIGN_BG_SLOT0 + i
        src_png = os.path.join(src_dir, stem + '.png')
        if not os.path.isfile(src_png):
            sys.exit('ERROR: campaign BG source missing: %s' % src_png)
        dst_png = os.path.join(BG_GFX_DIR, stem + '.png')
        shutil.copyfile(src_png, dst_png)
        for stale in ('.feimg2.bin', '.feimg2.bin.lz', '.fetsa2.bin',
                      '.fetsa2.bin.lz', '.gbapal'):
            if os.path.exists(dst_png[:-4] + stale):
                os.remove(dst_png[:-4] + stale)
        by_slot[slot] = (enum_name, stem)
        externs.append('extern unsigned char %s_tiles[];\n'
                       'extern unsigned char %s_map[];\n'
                       'extern unsigned char %s_palette[];' % (stem, stem, stem))
        data_syms.append(
            '\n\t.align 2, 0\n\t.global %(s)s_tiles\n%(s)s_tiles:\n'
            '\t.incbin "graphics/bg/%(s)s.feimg2.bin.lz"\n'
            '\n\t.align 2, 0\n\t.global %(s)s_map\n%(s)s_map:\n'
            '\t.incbin "graphics/bg/%(s)s.fetsa2.bin"\n'
            '\n\t.align 2, 0\n\t.global %(s)s_palette\n%(s)s_palette:\n'
            '\t.incbin "graphics/bg/%(s)s.gbapal"\n' % {'s': stem})
    # 1. enum ids: campaign BGs live PAST BG_RANDOM (0x37) -> insert AFTER its line (keeps the
    #    table index == enum value, and never renumbers the vanilla sentinel).
    enum_lines = ['    %s = 0x%X,' % (by_slot[s][0], s) for s in sorted(by_slot)]
    with open(BACKGROUNDS_H, encoding='utf-8') as f:
        h = f.read()
    anchor = next((ln for ln in h.splitlines() if ln.strip().startswith('BG_RANDOM')), None)
    if anchor is None or h.count(anchor) != 1:
        sys.exit('ERROR: BG_RANDOM enum anchor not unique in %s' % BACKGROUNDS_H)
    h = h.replace(anchor, anchor + '\n' + '\n'.join(enum_lines), 1)
    with open(BACKGROUNDS_H, 'w', encoding='utf-8') as f:
        f.write(h)
    # 2. table rows: append after bg_Blank (0x35) up to the highest campaign slot. Indices with
    #    no campaign BG (the 0x36 gap + 0x37 BG_RANDOM) get a harmless bg_Blank placeholder row
    #    so the table stays index==enum contiguous; BG_RANDOM never hits it (eventscr.c short-
    #    circuits on `bgIndex == BG_RANDOM` before any table lookup).
    placeholder = '\t{bg_Blank_tiles, bg_Blank_map, bg_Blank_palette},'
    table_rows = []
    for idx in range(0x36, max(by_slot) + 1):
        if idx in by_slot:
            s = by_slot[idx][1]
            table_rows.append('\t{%s_tiles, %s_map, %s_palette},' % (s, s, s))
        else:
            table_rows.append('%s /* 0x%X: BG_RANDOM / gap placeholder (never drawn) */' % (placeholder, idx))
    tail = placeholder + '\n};'
    with open(EVENTSCR2_C, encoding='utf-8') as f:
        c = f.read()
    if c.count(tail) != 1:
        sys.exit('ERROR: gConvoBackgroundData tail not in expected form in %s' % EVENTSCR2_C)
    c = c.replace(tail, placeholder + '\n' + '\n'.join(table_rows) + '\n};', 1)
    with open(EVENTSCR2_C, 'w', encoding='utf-8') as f:
        f.write(c)
    # 3. externs: the table rows reference the data_bg symbols -- declare them in bg.h.
    decl_anchor = 'extern unsigned char bg_Blank_palette[];'
    with open(BG_H, encoding='utf-8') as f:
        bh = f.read()
    if bh.count(decl_anchor) != 1:
        sys.exit('ERROR: bg.h extern anchor not unique in %s' % BG_H)
    bh = bh.replace(decl_anchor, decl_anchor + '\n' + '\n'.join(externs), 1)
    with open(BG_H, 'w', encoding='utf-8') as f:
        f.write(bh)
    # 4. incbin symbols: append to data_bg.s (the bins are make-built from the PNG).
    with open(DATA_BG_S, encoding='utf-8') as f:
        d = f.read()
    with open(DATA_BG_S, 'w', encoding='utf-8') as f:
        f.write(d + ''.join(data_syms))
    if verbose:
        print('  %d campaign BG(s) -> gConvoBackgroundData[0x%X..] (additive)'
              % (len(CAMPAIGN_BGS), CAMPAIGN_BG_SLOT0))


def inject_ch02(campaign, verbose=True):
    """Wire Ch2 "Cold Welcome" (#22) onto chapter slot 3 (ch01's MNC2(0x3) target).

    Simpler than inject_ch01: the founding party PERSISTS from ch01 (no cast re-LOAD, no
    lord-select menu) -- only the ch01 cutscene recruit Baxby gets an explicit off-map
    join-LOAD here (step 2a-bis), his first prep roster. The win is DefeatAll (no Seize). The slot-3 host goal is
    swapped to vanilla slot-4's defeat_all template, the vanilla Ch3 Seize(14,1) is
    dropped (so engine CountRedUnits() drives the rout win), and the ch01-chosen lord
    is auto-force-deployed by the flag-driven IsCharacterForceDeployed_ hook
    (_inject_lord_select_engine) -- no per-chapter wiring beyond the
    CauseGameOverIfLordDies that already sits in EventListScr_Ch3_Misc.

    The protect layer is three GREEN chwinga (pegasus chassis, vanilla Colm table
    088B4718 repurposed) on distinct NPC slots; each surviving chwinga gifts a charm
    (Red Gem / Elixir / Pure Water) at the ending scene via CHECK_ALIVE -> GIVEITEMTO
    (per-unit soft-fail, no game over). Enemies are vanilla Ch2's exact mix, reflavored
    chardalyn berserkers. Reinforcements move to the empty table 088B4758 (088B4718 is
    now the chwinga).

    DEFERRED checkpoints (flagged, not in this pass): the DIALOGUE REGROUND -- the locked
    cutscene text still frames the dropped sled + "snow wolves" and lacks a chwinga intro
    beat (Nicolas co-write via the dialogue-pass skill; wired as placeholder meanwhile);
    the chwinga art (map sprite + portrait + name-text over DARA/KLIMT/MANSEL, #38/#39);
    Vellynne's cutscene bust (#19, placeholder vanilla face here); the chardalyn map-sprite
    reskin (vanilla brigand sprite for now); and the in-game load-test.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH02_CHAPTER_YAML)

    # 0. Cutscene beat splits, consumed from the locked chapter YAML (cf. inject_ch01).
    op_card, op_beats = _split_event_beats(chap, 'chapter_start', 'ch02 opening',
                                           CH02_OPENING_MSGS, card_required=False)
    end_card, end_beats = _split_event_beats(chap, 'chapter_end', 'ch02 ending',
                                             CH02_ENDING_MSGS, card_required=False)
    bark = next(e for e in chap['events']
                if e.get('trigger') == 'turn_start' and e.get('turn') == 3)['script']
    tutorial = next(e for e in chap['events']
                    if e.get('trigger') == 'turn_start' and e.get('turn') == 1)['script']
    if len(tutorial) != len(CH02_TUTORIAL_MSGS):
        sys.exit('ERROR: ch02 turn-1 tutorial has %d lines; expected %d '
                 '(zip would silently drop the extra)' % (len(tutorial), len(CH02_TUTORIAL_MSGS)))

    cut_special = {
        'narration': None,                         # faceless stage-business box (#58)
        'vellynne': _fid_tag(CH02_VELLYNNE_SLOT),  # recurring NPC: placeholder face (#19)
        'targos-fisher': CH02_FISHER_FID,          # generic villager mug
    }

    cut_fid = _make_fid(cut_special, 'ch02 unknown cutscene speaker')

    # Vellynne anchors mid-right (the quest-giver, cf. Hlin/Duvessa); everyone else
    # speaks from mid-left. The ending beats are single-speaker each, so mid-left is
    # enough (no two-shots, no preloads -> no REMA face-flashing, cf. inject_ch01).
    op_home = {'vellynne': '[OpenMidRight]'}

    # 1. Map: register the painted layout, point slot 3 at it + the winter tileset, and
    #    swap the host goal to vanilla slot-4's defeat_all template (cf. inject_ch01 step 1).
    indices = _register_chapter_map(maps_dir, CH02_LAYOUT,
                                    'Manchego Stars ch02 layout (#22)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH02_HOST_INDEX, 4, 'defeat_all',
        'ERROR: slot 4 goal is not the vanilla defeat_all template '
        '(needed as the ch02 DefeatAll donor)',
        indices, chap['chapter_number'], CH02_EVENT_GROUP,
        (CH02_GOAL_WINDOW_MSG, CH02_GOAL_STATUS_MSG))

    # 2. Rosters (events_udefs.c). Four tables, reusing vanilla Ch3 symbols (already
    #    declared in eventcall.h, so no extern surgery):
    #    - UnitDef_Event_Ch3Ally: the 5-slot deploy template = THE CAP. Never LOADed;
    #      the prep flow reads its entry count (cap) + positions (deploy tiles). The
    #      founding party itself persists from ch01 (no join-LOAD) -- but a cutscene recruit
    #      (Baxby) was never a unit, so he needs an explicit join-LOAD (UnitDef_088B476C, 2a-bis).
    #    - UnitDef_088B463C: the RED raider band (Beginning-scene LOAD1) -- vanilla Ch2's
    #      exact mix, reflavored chardalyn berserkers. 0x8e = generic autolevelled trash;
    #      Grukk rides the vanilla Bone slot, Halvar the Bazba slot.
    #    - UnitDef_088B4718: the 3 GREEN chwinga (LOAD1 at chapter start, green from .allegiance;
    #      was vanilla Colm's green table). Distinct NPC slots so CHECK_ALIVE tracks each.
    #    - UnitDef_088B4758: the turn-3 RED reinforcement pair (the empty vanilla table;
    #      088B4718 is now the chwinga). Vanilla 088B4470 mix = one L2 + one L3 brigand.
    # available_at=2: the party on the field at ch02 -- founding party + Baxby (recruited
    # ch01 at the market); Trex (ch03) is not yet in. Data-driven from each unit's recruit.chapter.
    # NB this only SIZES the deploy cap; the founding party persists from ch01 but Baxby (a
    # cutscene recruit) is put in the saved roster by the off-map join-LOAD below (2a-bis, #23).
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    deploy = _deploy_cap_entries(chap, cast, leader, 'ch02')

    # 2a-bis. Off-map recruit join-LOAD: the party persists from ch01 (already in the save),
    #     but a cutscene recruit was never a unit -- so LOAD him in HERE, his first prep
    #     roster, or the deploy cap sizes a slot nothing fills (#23). For ch02 that is Baxby
    #     (ch01 ending cutscene; recruit.via = market = off-map). Each rides its CLASS_LOADOUT
    #     kit, blue, on a walkable NW tile (PREP re-picks positions). Empty for a chapter with
    #     no newly-available off-map recruit (then no LOAD1 is emitted -- see step 4).
    join_recruits = offmap_join_recruits(campaign, chap['chapter_number'])
    for uid, _s, ce, _d, _l in join_recruits:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch02 join recruit %s)' % (ce, uid))
    jx, jy = CH02_RECRUIT_JOIN_POS
    recruit_join = [_ally_unit_entry(leader, slot, dce, lv, jx, jy,
                                     ', '.join(CLASS_LOADOUT[ce]),
                                     ' /* %s -- off-map recruit joins the party (#23) */' % uid)
                    for uid, slot, ce, dce, lv in join_recruits]

    by_eid = {e['id']: e for e in chap['enemy_units']}
    raider = by_eid['chardalyn-raider']            # 2x L3 generic brigand (vanilla #1 + #5)
    scavenger = by_eid['chardalyn-scavenger']      # 1x L3, the vulnerary dropper (vanilla #4)
    skirmisher = by_eid['chardalyn-skirmisher']    # 1x L2 generic brigand (vanilla #6)
    archer = by_eid['frost-archer']                # 1x L1 archer (vanilla #2)
    grukk, halvar = by_eid['raider-bruiser'], by_eid['raider-captain']
    reinf = chap['reinforcements'][0]
    brig, arch = CH02_CLASS_IDS['brigand'], CH02_CLASS_IDS['archer']
    axe, steel, bow, vuln, lance = (CH02_ITEM_IDS['iron-axe'], CH02_ITEM_IDS['steel-axe'],
                                    CH02_ITEM_IDS['iron-bow'], CH02_ITEM_IDS['vulnerary'],
                                    CH02_ITEM_IDS['slim-lance'])

    # 2a. RED raider band (088B463C) -- vanilla Ch2 parity, reflavored chardalyn berserkers.
    enemies = []
    for x, y in raider['positions']:
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, brig, raider['level'], True, x, y,
            axe, CH02_AI['aggressive'], ' /* chardalyn berserker */'))
    for x, y in scavenger['positions']:
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, brig, scavenger['level'], True, x, y,
            '%s, %s' % (axe, vuln), CH02_AI['aggressive'],
            ' /* chardalyn scavenger -- drops the vulnerary */',
            itemdrop=True))
    for x, y in skirmisher['positions']:
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, brig, skirmisher['level'], True, x, y,
            axe, CH02_AI['aggressive'], ' /* chardalyn skirmisher (L2) */'))
    for x, y in archer['positions']:
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, arch, archer['level'], True, x, y,
            bow, CH02_AI['aggressive'],
            ' /* chardalyn hunter (archer) -- hard-counters the pegasi */'))
    gx, gy = grukk['position']
    enemies.append(_enemy_unit_entry(
        'CHARACTER_%s' % CH02_MINIBOSS_SLOT, brig, grukk['level'],
        False, gx, gy, axe, CH02_AI['hold_position'],
        ' /* Grukk the Bruiser -- miniboss, fixed bases (Bone slot) */'))
    hx, hy = halvar['position']
    enemies.append(_enemy_unit_entry(
        'CHARACTER_%s' % CH02_BOSS_SLOT, brig, halvar['level'],
        True, hx, hy, steel, CH02_AI['hold_position'],
        ' /* Halvar the Raider Captain -- boss, steel axe (Bazba slot) */'))

    # 2b. GREEN chwinga (088B4718) -- the protect layer; class + level + positions +
    #     per-survivor gift come from the YAML deployment.green_allies (id order
    #     matches CH02_CHWINGA). autolevel leans on the class curve (bases = tuning
    #     checkpoint).
    chwinga_by_id = {g['id']: g for g in chap['deployment']['green_allies']}
    # The charm-gift is authored in the YAML (green_allies[].gift) -- the single source of truth
    # for the ch02<->ch03 reward swap. Validate every gift resolves + the id sets agree, so a YAML
    # edit that adds/renames a gift fails loudly here instead of silently shipping the wrong item.
    for uid, _slot in CH02_CHWINGA:
        g = chwinga_by_id.get(uid)
        if not g or 'gift' not in g:
            sys.exit('ERROR: ch02 chwinga %s missing from deployment.green_allies or has no gift' % uid)
        if g['gift'] not in CH02_ITEM_IDS:
            sys.exit('ERROR: ch02 chwinga %s gift %r not in CH02_ITEM_IDS' % (uid, g['gift']))
    chwinga = [_ally_unit_entry(None, slot,
                                CH02_CLASS_IDS[chwinga_by_id[uid]['class']],
                                chwinga_by_id[uid]['level'],
                                chwinga_by_id[uid]['position'][0],
                                chwinga_by_id[uid]['position'][1],
                                lance, ' /* chwinga %s (gift: %s) */' % (uid, chwinga_by_id[uid]['gift']),
                                allegiance='GREEN', autolevel=True,
                                ai=CH02_AI['cautious'])
               for uid, slot in CH02_CHWINGA]

    # 2c. RED reinforcements (088B4758) -- vanilla 088B4470 mix: one L2 + one L3, turn 3.
    reinforce = [_enemy_unit_entry(CH02_GENERIC_PID, brig, lv, True, x, y, axe,
                                   CH02_AI['reinforce'], ' /* rear raider L%d, turn %d */'
                                   % (lv, reinf['trigger_turn']))
                 for (x, y), lv in zip(reinf['positions'], reinf['levels'])]

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    tables = [('UnitDef_Event_Ch3Ally[] =', deploy),
              ('UnitDef_088B463C[] =', enemies),
              ('UnitDef_088B4718[] =', chwinga),
              ('UnitDef_088B4758[] =', reinforce)]
    if recruit_join:  # only overwrite the free join table when a recruit actually joins here
        tables.append(('%s[] =' % CH02_RECRUIT_JOIN_SYMBOL, recruit_join))
    for marker, entries in tables:
        block = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'
        udefs = _replace_brace_block(udefs, marker, block, EVENTS_UDEFS_C)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Event lists (ch3-eventinfo.h). Turn: the rear raiders on turn 3 (FACTION_ID_BLUE
    #    appear-at-player-phase idiom, cf. inject_ch01). Character/Location cleared: no
    #    talks, and DROP the vanilla Seize(14,1) + chests/doors so DefeatAll (CountRedUnits)
    #    is the only win path. Misc keeps its vanilla CauseGameOverIfLordDies untouched.
    with open(CH3_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    info = _replace_brace_block(
        info, 'EventListScr_Ch3_Turn[] =',
        '{\n    TURN(0x0, EventScr_Ch3_Turn2Player, 1, 0, FACTION_ID_BLUE)'
        ' /* turn-1 fliers-vs-bows: RBG warns flier Pinky off the archer */\n'
        '    TURN(0x0, EventScr_Ch3_Turn1Npc, %d, 0, FACTION_ID_BLUE)'
        ' /* turn-%d rear raiders + Wolfram bark */\n    END_MAIN\n}'
        % (reinf['trigger_turn'], reinf['trigger_turn']), CH3_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch3_Character[] =', '{\n    END_MAIN\n}', CH3_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch3_Location[] =', '{\n    END_MAIN\n}', CH3_EVENTINFO_H)
    with open(CH3_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # 4. Scenes (ch3-eventscript.h). Beginning: Vellynne's opening over a scenic BACG,
    #    then LOMA rebuilds the battle map fresh (the BACG clobbered it, cf. inject_ch01),
    #    the raiders LOAD, and the shared prep call runs Pick Units (cap 5, lord
    #    force-deployed). Turn1Npc: the turn-3 reinforcement LOAD + Wolfram's bark over the
    #    map. Ending: the Targos discovery, then the dev placeholder (ch03 not hosted yet).
    op_text_calls = _scenic_beat_calls(
        CH02_OPENING_MSGS, op_beats,
        ['A -- Vellynne stops them; RBG haggles the orb job',
         'B -- Meesmickle & Braulo react to the corpse-sled',
         'C -- Sclorbo meets his chwinga kin; Marty offers a Chagaccino'])
    tut_text_calls = _scenic_beat_calls(
        CH02_TUTORIAL_MSGS, [[ln] for ln in tutorial],
        ['RBG warns flier Pinky off the archer (fliers-vs-bows debut)',
         'Pinky takes it to heart'])
    end_text_calls = _scenic_beat_calls(
        CH02_ENDING_MSGS, end_beats,
        ['A -- the Targos fisher warns them off the frozen body',
         'B -- Rootis clocks the dagger-of-ice kill (Sephek breadcrumb)',
         'C -- nightfall narration over the camp (#58 opaque box)',
         'D -- RBG sets the road north (lets the Bremen bounty keep)'])
    # Off-map recruit join-LOAD line: emitted only when a cutscene/market recruit becomes
    # available this chapter (Baxby, ch02) -> he enters the persistent party right before PREP,
    # so Pick Units lists him. Empty (no LOAD1) for a chapter with no such recruit.
    recruit_load = (
        '    LOAD1(0x1, %s) /* off-map recruit joins the persistent party (#23) */\n'
        % CH02_RECRUIT_JOIN_SYMBOL if recruit_join else '')
    with open(CH3_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    script = _replace_brace_block(
        script, 'EventScr_Ch3_BeginningScene[] =',
        '{\n'
        '    MUSC(SONG_TENSION)\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(%s) /* Bryn Shander west gate (placeholder BG; #22 polish) */\n'
        '    FADU(16)\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "Bryn Shander -- West Gate" card */\n'
        % (CH02_OPENING_BG, CH02_OPENING_CARD_MSG)
        + op_text_calls +
        ('    FADI(16) /* fade the scenic BG out */\n'
         '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin */\n'
         '    LOMA(0x%X) /* RestartBattleMap -- build the ch02 map fresh (cf. inject_ch01) */\n'
         '    LOAD1(0x1, UnitDef_088B463C) /* the RED raider band */\n'
         '    LOAD1(0x1, UnitDef_088B4718) /* the 3 GREEN chwinga (protect layer) */\n'
         % CH02_HOST_INDEX)
        + recruit_load +
        '    ENUN\n'
        # NO FADU here: the prep prologue (EventScr_08591F64) fades to black before drawing
        # Preparations, so revealing the map first only FLASHES it. Stay black into CALL(prep).
        '    CALL(EventScr_08591FD8) /* preparations (PREP, event cmd 0x3E) -- cap 5 */\n'
        '    ENUT(8)\n'
        '    EVBIT_T(7)\n'
        '    ENDA\n}', CH3_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch3_Turn1Npc[] =',
        '{\n    SVAL(EVT_SLOT_2, UnitDef_088B4758)\n'
        '    CALL(EventScr_LoadReinforce)\n'
        '    TEXTSHOW(0x%X) /* Wolfram: hold the rear (rear-ambush bark) */\n'
        '    TEXTEND\n    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}' % CH02_BARK_MSG, CH3_EVENTSCRIPT_H)
    # Turn-1 fliers-vs-bows tutorial (repurposes the dead vanilla Ch3 Turn2Player scene):
    # RBG warns flier Pinky off the Chardalyn Hunter -- the in-voice heads-up vanilla owes
    # via the Vanessa rescue. Portrait talk over the map; no BACG (would clobber the map).
    script = _replace_brace_block(
        script, 'EventScr_Ch3_Turn2Player[] =',
        '{\n' + tut_text_calls +
        '    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}', CH3_EVENTSCRIPT_H)
    # Per-chwinga charm-gift: read each chwinga's survival (CHECK_ALIVE writes EVT_SLOT_C)
    # while the battle units are still loaded, BEQ past the give if it fell, else drop the
    # charm into the leader's inventory (overflow -> convoy). This is the chapter's
    # per-unit soft-fail signature beat (cf. vanilla survival idiom, ch10b ending).
    chwinga_gifts = ''.join(
        '    SVAL(EVT_SLOT_3, %s) /* %s charm */\n'
        '    CHECK_ALIVE(CHARACTER_%s)\n'
        '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* fell -> forfeit its own charm */\n'
        '    GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)\n'
        'LABEL(0x%X)\n'
        % (CH02_ITEM_IDS[chwinga_by_id[uid]['gift']], uid, slot.upper(), 0x30 + i, 0x30 + i)
        for i, (uid, slot) in enumerate(CH02_CHWINGA))
    script = _replace_brace_block(
        script, 'EventScr_Ch3_EndingScene[] =',
        '{\n    MUSC(SONG_VICTORY)\n'
        + chwinga_gifts +               # per-survivor charm-gifts (read while units are loaded)
        '    REMOVEPORTRAITS\n'
        '    BACG(%s) /* Targos square (placeholder BG; #22 polish) */\n'
        '    FADU(16)\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "Targos" card */\n'
        % (CH02_ENDING_BG, CH02_ENDING_CARD_MSG)
        + end_text_calls +
        '    FADI(16) /* fade the town out */\n'
        '    MNC2(0x%X) /* -> ch03 "The Termalaine Mine", hosted on chapter slot 4 (inject_ch03) */\n'
        '    ENDA\n}' % CH03_HOST_INDEX, CH3_EVENTSCRIPT_H)
    with open(CH3_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 5. Halvar's defeat quote -> head of gDefeatTalkList (same shadowing rule as ch01:
    #    a head entry wins the first-match scan, shadowing any vanilla Bazba entry).
    quote = ('    {\n'
             '        .pid     = CHARACTER_%s, /* Halvar death quote (ch02) */\n'
             '        .route   = CHAPTER_MODE_ANY,\n'
             '        .chapter = CHAPTER_L_3, /* ch02 is hosted on chapter slot 3 */\n'
             '        .msg     = 0x%X,\n'
             '    },' % (CH02_BOSS_SLOT, CH02_BOSS_DEATH_MSG))
    _prepend_defeat_quote(quote)

    # 6. Texts. Overwritten ids are dead vanilla Ch3 scene/talk/turn messages (the vanilla
    #    Ch3 scenes are gone); 0x993/0x994 are LIVE battle quotes and are NOT in the pool.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    # Boss/miniboss ride vanilla slots (Bazba/Bone) -- rename their name plates to ours,
    # or the vanilla "Bazba"/"Bone" leaks on the unit window + death quote (cf. inject_ch01,
    # which renames its Breguet boss slot). display_name uses the YAML fe_name (<=12).
    set_message_body(lines, vanilla_name_text_id(CH02_BOSS_SLOT),
                     name_message_body(display_name(halvar)))
    set_message_body(lines, vanilla_name_text_id(CH02_MINIBOSS_SLOT),
                     name_message_body(display_name(grukk)))
    # VANILLA'S OWN WORDING, restored 2026-07-31 (Nicolas: "it should never have been altered
    # in the first place"). FE8 never prints "rout" as an objective -- its whole objective
    # vocabulary is Defeat enemy / Defeat boss / Defeat all monsters / Seize gate / Seize throne
    # / Survive, and the game's only uses of the word are "Route +/-" on the world map and
    # "en route" in prose. "Rout" is FE *community* vocabulary, and importing it also overran a
    # window vanilla had sized for its own words.
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat all monsters'))
    set_message_body(lines, host['goal']['windowTextId'],
                     goal_window_body('Defeat enemy'))
    set_message_body(lines, CH02_OPENING_CARD_MSG, name_message_body(op_card))
    _emit_scene_beats(lines, CH02_OPENING_MSGS, op_beats, cut_fid, op_home)
    # Turn-1 fliers-vs-bows tutorial: one portrait box per line (RBG, then Pinky), Text_BG 42-wrap.
    for msg_id, ln in zip(CH02_TUTORIAL_MSGS, tutorial):
        set_message_body(lines, msg_id, _script_to_message(
            [ln], _stage_beat([ln], cut_fid, op_home), width=42))
    # Wolfram's rear-ambush bark, shown over the map (29-tile bubble wrap via
    # _wrap_fe_lines; the current YAML lines fit unwrapped).
    set_message_body(lines, CH02_BARK_MSG, _script_to_message(
        bark, {'wolfram': ('[OpenMidLeft]', _fid_tag(PORTRAIT_MAP['wolfram'].upper()))},
        width=29))
    set_message_body(lines, CH02_ENDING_CARD_MSG, name_message_body(end_card))
    _emit_scene_beats(lines, CH02_ENDING_MSGS, end_beats, cut_fid, {})
    set_message_body(lines, CH02_BOSS_DEATH_MSG, _script_to_message(
        [{'halvar': halvar['death_quote']}],
        {'halvar': ('[OpenMidRight]', _fid_tag(CH02_BOSS_SLOT))}, width=29))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 6a. Title card image (the intro/status banner is a 4bpp image, not text) -- "Ch.2:
    #     <title>" composed from vanilla glyphs (gen_chapter_title reads the source cards
    #     from HEAD, so inject_ch01 overwriting chap_title_2.png first doesn't disturb the
    #     "Ch.2:" cut).
    _write_chapter_title_card(host, 'Ch.2: ' + chap['title'])

    if verbose:
        print('  ch02 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'DefeatAll, deploy cap %d + PREP (lord auto-force-deployed)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH02_HOST_INDEX, len(deploy)))
        joined = ', '.join(uid for uid, *_ in join_recruits) or 'none'
        print('  rosters: party persists + off-map recruit join-LOAD [%s], %d chardalyn '
              'raiders (Grukk@%s Halvar@%s) + %d rear raiders turn %d; %d GREEN chwinga '
              '(per-survivor charm-gifts)'
              % (joined, len(enemies), (gx, gy), (hx, hy), len(reinforce),
                 reinf['trigger_turn'], len(chwinga)))


# ── Ch3 "The Termalaine Mine" (#23): hosted on chapter slot 4 (repaint of vanilla Ch3
#    "Bandits of Borgo", so the roster/positions mirror vanilla Ch3 1:1). Uses the vanilla
#    "Ch4" decomp symbol set (host index N -> ChN symbols, cf. ch02 on slot 3 = Ch3 symbols).
# CH03_HOST_INDEX / CH03_EVENT_GROUP: inject/hosts.py.
CH03_GOAL_WINDOW_MSG = 0x19D     # vanilla slot 6's defeat_boss window
CH03_GOAL_STATUS_MSG = 0x1A7
CH03_LAYOUT = ('Ch03TermalaineMineMap', 'ch03-the-termalaine-mine')  # (asset label, maps/ stem)
CH03_CHAPTER_YAML = 'ch03-the-termalaine-mine.yaml'
CH03_TILESET = 'cave-interior'   # stem 'Cave' (TILESET_STEMS); first chapter to use it -> self-registers
CH03_GOAL_DONOR = 6              # vanilla slot 6 = defeat_boss goal template (untouched by our injectors)
CH03_BOSS_PID = '0xb7'          # grell rides a raw charIndex (NOT the vanilla ch4 boss ENTOUMBED_CH4=0x49):
                                # a clean slate -- no vanilla boss name/face/defeat-quote leaks, and our
                                # flagged gDefeatTalkList entry (CHAPTER_L_4) uniquely keys the DefeatBoss win to it.
CH03_GENERIC_PID = '0xaa'       # vanilla slot-4 generic-minion charIndex (autolevelled trash)
# The grell's flagged death quote (gDefeatTalkList) sets EVFLAG_DEFEAT_BOSS -> the Misc DefeatBoss AFEV.
# Body rides a dead vanilla Ch4 message id: 0x9A3 is the Ch4 opening cutscene's first line (Seth/Eirika at
# Serafew), referenced ONLY inside EventScr_Ch4_BeginningScene -- which inject_ch03 replaces -> dead in our build.
CH03_BOSS_DEATH_MSG = 0x9A3
# DefeatBoss ending script: repurpose the vanilla Ch4 ending EventScr_089F19F8 (defined in ch4-eventscript.h,
# already extern-referenced by the vanilla Ch4 Misc's DefeatAll -> visible to ch4-eventinfo.h's Misc list).
CH03_ENDING_SCRIPT = 'EventScr_089F19F8'
CH03_AI = {'aggressive': '{0x0, 0x0, 0x1, 0x0}',   # pursue/charge
           'defensive':  '{0x3, 0x3, 0x9, 0x20}'}  # attack in place, never move (hold the galleries)
# Brigand kobolds ride the Lizard-Wildling reskin slot (inject_enemy_class_reskins clones
# CLASS_BRIGAND -> CLASS_BRG_LIZARD_WILDLING, an appended class id, with the lizard SMS;
# combat stays brigand). Grell = vanilla Mogall; blade = Mercenary (Lizardzerker slot lands
# next); archer/thief stay vanilla.
CH03_CLASS_IDS = {'mogall': 'CLASS_MOGALL', 'brigand': 'CLASS_BRG_LIZARD_WILDLING',
                  'mercenary': 'CLASS_MNC_LIZARDZERKER', 'archer': 'CLASS_ARCHER',
                  'thief': 'CLASS_THIEF',
                  # the steel brute: a Brigand (parity) that DEPLOYS on the Lizardzerker
                  # sprite via a brigand-clone class (campaign.yaml kobold-brute). Reached
                  # through an enemy's `deploy_class` override, not its `class`.
                  'brigand-brute': 'CLASS_MNC_LIZARDZERKER_BRUTE'}
CH03_ITEM_IDS = {'iron-axe': 'ITEM_AXE_IRON', 'hand-axe': 'ITEM_AXE_HANDAXE',
                 'steel-axe': 'ITEM_AXE_STEEL', 'iron-sword': 'ITEM_SWORD_IRON',
                 'iron-lance': 'ITEM_LANCE_IRON', 'javelin': 'ITEM_LANCE_JAVELIN',
                 'iron-bow': 'ITEM_BOW_IRON', 'evil-eye': 'ITEM_MONSTER_EVILEYE',
                 'red-gem': 'ITEM_REDGEM',
                 'pure-water': 'ITEM_PUREWATER', 'antitoxin': 'ITEM_ANTITOXIN',
                 'door-key': 'ITEM_DOORKEY', 'chest-key': 'ITEM_CHESTKEY'}
# The FF5 navy chest metatile in the cave-interior tileset (retile.py): closed 17 / open 29.
# gBmMapBaseTiles stores metatile<<2 (compile_layout: .mar = metatile<<5, mar_to_map >>3, so
# the loaded tile = metatile<<2), so the open-chest tile a MapChange writes is 29<<2 (#23).
CH03_CHEST_CLOSED_TILE = 17
CH03_CHEST_OPEN_TILE = 29
# Left-entrance floor tiles (verified walkable on the painted .mar, clear of enemy tiles) --
# the party deploys here statically (fast-boot; the real PREP flow lands with deploy_slots + cutscenes).
# 9 tiles = the ch03 field roster (cast_available_at(3) = the 8 founding party + Baxby, the
# ch01 recruit). Trex is NOT here -- he is a Colm-style TALK recruit placed GREEN on the map
# (CH03_TREX_GREEN_POS), joining via CUSA when a party member talks to him (that CHAR talk +
# its line ride the ch03 event/cutscene pass, #23 item 4). cast_available_at gives him ch04+ prep.
CH03_TREX_GREEN_POS = (2, 4)    # Colm's tile: our map is a 1:1 17x16 retile of vanilla Ch3 (Borgo),
                                # where green Colm walks to (2,4) on the upper-left ledge (spawns 0,5)
                                # -- UnitDef_088B4718/REDA_088B456C. Trex mirrors the recruit, so he
                                # stands green on the same ledge the party naturally reaches to Talk.
# Two free vanilla Ch4 UnitDef tables (defined in events_udefs.c, referenced nowhere but
# themselves -> safe to repurpose, like the enemy table 088B4A80): one holds Trex GREEN
# (always LOADed, the on-map talk-recruit); the other is the DEBUG-BOOT party seed (the
# armed field roster, LOADed ONLY on --ch03-boot to found a party from nothing so PREP has
# something to pick -- exactly ch01's founding-chapter shape). The real chain (item 3) omits
# the seed: the party persists from ch02, and PREP reads the never-LOADed cap template.
CH03_TREX_GREEN_SYMBOL = 'UnitDef_088B49CC'
CH03_BOOT_SEED_SYMBOL = 'UnitDef_088B47E4'
CH03_PREP_SCRIPT = 'EventScr_08591FD8'   # shared Preparations call (event cmd 0x3E), cf. ch01/ch02
# Trex talk-recruit wiring (#23 item 2) -- the vanilla Colm/Neimi pattern. Repurpose dead
# vanilla Ch4 symbols the host frees: EventScr_089F199C is the Ch4 Turn-2 green script (its
# only referrer was EventListScr_Ch4_Turn, emptied by the host) -> the shared recruit script;
# 0x9A5 is a dead Ch4 opening-cutscene line (referenced only by the replaced BeginningScene,
# like the boss-death 0x9A3) -> the talk body; EVFLAG_TMP(9) is vanilla ch3 Colm's own CHAR
# talk flag, unused in our minimal host.
CH03_TREX_TALK_SCRIPT = 'EventScr_089F199C'
CH03_TREX_TALK_MSG = 0x9A5
CH03_TREX_TALK_FLAG = 'EVFLAG_TMP(9)'
# ch03 cutscene beats (#23 Cutscenes) ride the dead vanilla Ch4 cutscene-message block
# 0x9A3..0x9B9 -- every id there is referenced ONLY by the Ch4 event scripts that inject_ch03
# replaces (git-verified against the pristine ch4-eventscript.h) -> dead in our build. 0x9A3
# (boss death) + 0x9A5 (talk) are already claimed above. BG: reuse the ch02 Targos-winter slot
# for the Termalaine street (Nicolas 2026-07-04: vanilla-style BG reuse, no new slot; the
# mid-map beats play ON-MAP, no BG). The midmap RBG-execution beat uses 0x9AF..0x9B1 + 0x9B4
# (0x9B2/0x9B3 are the opening's Pinky-scout beats).
CH03_OPENING_TOWN_BG = 'BG_MS_TARGOS_WINTER'      # beats A-B: the Termalaine street (crier, bounty, Wolfram)
CH03_OPENING_MINE_BG = 'BG_MS_TERMALAINE_MINE'    # beats C-E: inside the mine (sign, Pinky's scout) -- swaps in after Wolfram's "we're going in"
CH03_OPENING_CARD_MSG = 0x9A6
# A crier/RBG · B Wolfram (town) -> BG swaps to the mine · C KOBOLDS-ONLY sign (#58 box, empty cave)
# · D Pinky scouts out (fades away) · E Pinky returns ("it looked at me")
CH03_OPENING_MSGS = (0x9A7, 0x9A8, 0x9A9, 0x9B2, 0x9B3)
CH03_ENDING_BG = 'BG_MS_TARGOS_WINTER'
CH03_ENDING_CARD_MSG = 0x9AA
CH03_ENDING_MSGS = (0x9AB, 0x9AC, 0x9AD)    # A RBG bounty · B Trex negotiates his warren in · C Meesmickle button
CH03_TREX_ENTRANCE_MSG = 0x9AE              # light turn-1 on-map beat (Pinky telegraph + RBG "little dragon")
CH03_TREX_ENTRANCE_SCRIPT = 'EventScr_089F1B38'  # dead Ch4 Village script (its list ref is dropped by the host) -> Trex's light turn-1 entrance beat
# Midmap RBG-execution beat (#23 item 1): the Icewind Brute is a mid-map MINIBOSS whose DEFEAT
# fires a flagged death cutscene (RBG guns down the beaten Brute) -- the mirror of the grell's
# DefeatBoss WIN, keyed to a tmp flag + a Misc AFEV instead of the win flag. It rides ON-MAP (no
# BG), like Trex's entrance. Reuses the dead Ch4 death-scene 0x9AF..0x9B1 message block.
CH03_BRUTE_MINIBOSS_PID = '0xb6'   # the Icewind Brute -- a clean raw charIndex sibling of the grell's
                                   # 0xb7 (0xB0..0xB9 are all UNNAMED gaps in gCharacterData, a
                                   # designated-init array -> zero name/face/quote, no vanilla leak).
                                   # Distinct from the shared generic 0xaa so its flagged death quote
                                   # keys the midmap trigger to the Brute ALONE (first-match pid scan).
CH03_BRUTE_DEFEAT_FLAG = 'EVFLAG_TMP(10)'  # set by the Brute's silent gDefeatTalkList entry on death
CH03_MIDMAP_GUARD_FLAG = 'EVFLAG_TMP(11)'  # AFEV ent-flag: guards the one-shot (set after the beat fires)
CH03_MIDMAP_SCRIPT = 'EventScr_089F1BD8'   # dead vanilla Ch4 script (defined-only; its list ref dropped by the host)
# 7 beats (RESTAGED 2026-07-11): A Pinky reaches out (faced) · A2 the Brute lunges at Pinky (FACELESS
# action box) · A3 the Brute's snarl (faced mug) · B RBG "Say cheese" (faced) · B2 the shot/kill (FACELESS
# action box) · B3 Pinky+RBG (faced two-hander) · C Wolfram (faced). The two faceless narration boxes ride
# the opaque auto-centered box (_beat_is_faceless -> SOLOTEXTBOXSTART). 0x9B2/0x9B3 are the opening's
# Pinky-scout beats; the midmap borrows 0x9B4..0x9B7 from the dead Ch4 block.
CH03_MIDMAP_MSGS = (0x9AF, 0x9B0, 0x9B1, 0x9B4, 0x9B5, 0x9B6, 0x9B7)
CH03_CRIER_FID = '[FID_VillagerYoungBoy]'   # the boy crying the bounty on his crate (book p.95; generic mug)
CH4_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch4-eventinfo.h')
CH4_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch4-eventscript.h')

# ── Ch4 "The White Moose" (#24): hosted on chapter slot 5. The authored snowy map
# preserves vanilla Ch4's 15x15 geometry, and the force preserves its 16 line + 7
# reinforcement pressure shape. The D&D creatures ground the encounter fiction, but
# player-facing units deliberately keep their vanilla FE8 monster identities/names.
# CH04_HOST_INDEX / CH04_EVENT_GROUP: inject/hosts.py. The group is NOT derivable from the
# slot index -- vanilla inserts chapter 5X at slot 5 -- and the registry says why.
CH04_LAYOUT = ('Ch04LonelywoodForestMap', 'ch04-lonelywood-forest')
CH04_CHAPTER_YAML = 'ch04-the-white-moose.yaml'
CH04_GOAL_DONOR = CH02_HOST_INDEX  # ch02 is already hosted with the stable DefeatAll/Rout goal.
                                   # It donates the goal TYPE only -- the text ids come from
                                   # CH04_GOAL_*_MSG, because inheriting this slot's is what made
                                   # ch02 and ch04 write over each other's objective (#207).
CH04_INITIAL_ENEMY_SYMBOL = 'UnitDef_088B56F8'
CH04_TURN2_SYMBOL = 'UnitDef_088B5798'
CH04_TURN3_SYMBOL = 'UnitDef_088B5914'
CH04_BOOT_SEED_SYMBOL = 'UnitDef_088B5978'
CH04_PREP_SCRIPT = 'EventScr_08591FD8'
CH04_ENDING_SCRIPT = 'EventScr_Ch5_EndingScene'
CH5_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch5-eventinfo.h')
CH5_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch5-eventscript.h')
CH04_CLASS_IDS = {
    'mauthedoog': 'CLASS_MAUTHEDOOG',
    'revenant': 'CLASS_REVENANT',
    'bonewalker': 'CLASS_BONEWALKER',
    'bonewalker-bow': 'CLASS_BONEWALKER_BOW',
    'mogall': 'CLASS_MOGALL',
    'entoumbed': 'CLASS_ENTOUMBED',
}
CH04_ITEM_IDS = {
    'rotten-claw': 'ITEM_MONSTER_ROTTENCLW',
    'iron-sword': 'ITEM_SWORD_IRON',
    'iron-lance': 'ITEM_LANCE_IRON',
    'iron-bow': 'ITEM_BOW_IRON',
    'iron-axe': 'ITEM_AXE_IRON',        # the Lonelywood village's reward (#205)
    'evil-eye': 'ITEM_MONSTER_EVILEYE',
    'fetid-claw': 'ITEM_MONSTER_FETIDCLW',
    'vulnerary': 'ITEM_VULNERARY',
}
# Vanilla Ch4 generic-monster charIds (read from events_udefs.s HEAD): the melee Revenant
# pack uses 0xaa, the melee Bonewalker pack 0xac -- the twin's own line/pack fodder pids.
CH04_MONSTER_PIDS = {
    'mauthedoog': '0xb3',
    'revenant': '0xaa',
    'bonewalker': '0xac',
    'bonewalker-bow': '0xad',
    'mogall': '0xb7',
    'entoumbed': '0xab',
}
CH04_AI = {
    'aggressive': '{0x0, 0x0, 0x1, 0x0}',
    'defensive': '{0x3, 0x3, 0x9, 0x20}',
}
# Stage 2b -- the turn-2 wolf-pack reveal + Marty->Lupin parley (issue #24). Lupin rides the
# collision-free Duessel identity slot (Stage 2a); placed RED as the pack leader, Marty's Talk
# CUSAs him blue and CUSNs the surviving generics green where they stand. The symbols/ids below
# are DEAD vanilla Ch5 slots -- unreachable once inject_ch04 blanks the Ch5 event lists, so we
# repurpose them (the same idiom ch03 uses for its dead-Ch4 block; each verified free by grep).
CH04_LUPIN_TALK_SCRIPT = 'EventScr_089F2340'  # dead Ch5 script -> the parley event
CH04_LUPIN_TALK_MSG = 0x9BA                    # dead Ch5 text slot -> stub parley line (Stage 4 finalizes)
CH04_LUPIN_TALK_FLAG = 'EVFLAG_TMP(9)'         # one-shot recruit flag (ch03's Colm-CHAR idiom)
# One pid PER generic wolf (#203). The pack used to share 0xb3, which made it unaddressable:
# CUSN and CHECK_ALIVE both resolve through GetUnitFromCharId (first match, scanning blue ->
# green -> red), so a second CUSN on a shared pid re-finds the wolf the first one just turned
# green -- which is why the parley had to DISA the pack and reload a green table on its SPAWN
# tiles. These five are the unnamed generic-monster gaps flanking the doog slot (0xB0..0xB9,
# the same band ch03's Brute/grell draw from): zero name/face/quote, personal bases and growths
# byte-identical to 0xb3's, and the wolf's CLASS comes from the unit definition (bmunit.c:697),
# so the split is invisible in play. Guarded by assert_pack_pids_addressable.
CH04_PACK_PIDS = ('0xb0', '0xb1', '0xb2', '0xb4', '0xb5')
CH04_PARLEY_LABEL_BASE = 0x40   # one skip label per wolf; the talk script has no other labels
CH04_GREEN_PACK_CLASS = 'CLASS_MTD_LYCANROC_PACK'  # campaign.yaml enemy_class_reskins: a Mauthe
                                               # Doog clone wearing the Lycanroc map sprite.
                                               # DECLARED BUT UNWORN since #203: converting the
                                               # pack in place flips its FACTION, not its class,
                                               # so the greens stay Mauthe Doogs in the NPC
                                               # palette. Kept for the class-remap hook that
                                               # will dress them later (Nicolas's accepted
                                               # trade-off, 2026-08-01).
# Stage 2c -- the turn-2 REVEAL cutscene rides the existing turn-2 TurnEvent script (it already
# LOADs the reveal table). Two dead Ch5 text slots for the stub beats (Stage 4 finalizes dialogue).
CH04_REVEAL_SCRIPT = 'EventScr_089F22A4'        # turn-2 TurnEventPlayer script (reused)
CH04_REVEAL_MSGS = (0x9BB, 0x9BC)               # Lupin command + Marty parley-flag (stubs)
CH04_REVEAL_CAMERA = (2, 2)                      # centre on the NW pack cluster

# ── Stage 4: the authored scenes ────────────────────────────────────────────────
# MESSAGE IDS: ch04 is hosted on slot 5, so it OWNS vanilla Ch5's whole message block
# (0x9BA-0x9CC) -- every id below is a dead Ch5 slot, freed when inject_ch04 blanks the Ch5
# event lists. ch05's YAML labels its beats "vanilla 0x9BB" etc., but those are ANATOMY
# references mined from its FE8 twin, NOT ids it may claim: ch05 will host on its own slot and
# take that slot's block. `_assert_message_ids_unique` (below) enforces this at build time --
# see the #198 review note on issue #24.
CH04_OPENING_CARD_MSG = 0x9BD                   # "Lonelywood" location card
CH04_OPENING_MSGS = (0x9BE, 0x9BF)              # A Nimsy's cottage · B the forest-edge fog beat
CH04_MOOSE_MSG = 0x9C0                          # the moose breaks and bolts -- RBG "After it!"
CH04_ENDING_MSG = 0x9C1                         # chapter_end, parley path (Lupin reads the trail)
CH04_ENDING_NO_LUPIN_MSG = 0x9C2                # chapter_end, no-parley path (Pinky/Meesmickle)
# Scene BGs. The cottage is vanilla FE8's House1 hearth interior and Nimsy rides the vanilla
# old-lady generic mug -- both DECIDED 2026-07-04 (Nicolas): in-ROM, so no vendored asset, no
# injection, no credit line. Beat B plays over a fogged plain (the scout who cannot see).
CH04_OPENING_COTTAGE_BG = 'BG_HOUSE'            # vanilla House1 -- Nimsy's hearth
CH04_OPENING_FOREST_BG = 'BG_MS_LONELYWOOD_FOG'  # the forest edge under fog (Pinky's beat) --
                                               # vanilla's bg_Plain_1 tiles on a winter palette
                                               # (BG_PLAIN_1_FOG is a GREEN meadow; the vanilla
                                               # "_FOG" variants are palette swaps, not art)
CH04_ENDING_BG = 'BG_FOREST'                    # dusk at the treeline; the sled at the ridge
CH04_NIMSY_FID = '[FID_VillagerOldWoman]'       # vanilla generic (textdefs.txt 0x5F)
# The moose: a scripted NEUTRAL that is sighted once and gone. It rides its own dead Ch5 slots.
CH04_MOOSE_SCRIPT = 'EventScr_089F2270'         # dead Ch5 script (vanilla's Natasha/Joshua Talk;
                                                #   its only ref is the Ch5 Character list, which
                                                #   inject_ch04 replaces) -> the moose-flees beat
CH04_MOOSE_SYMBOL = 'UnitDef_088B58D8'          # dead Ch5 unit table (referenced only from
                                                #   EventScr_089F2304, a Ch5 reinforcement script
                                                #   whose Turn entry we drop) -> the neutral moose
CH04_MOOSE_PID = '0xce'                         # its own pid (DISA targets it, and it alone)
CH04_MOOSE_GUARD_FLAG = 'EVFLAG_TMP(10)'        # AREA one-shot guard (must differ from the talk flag)
CH04_MOOSE_CLASS = 'CLASS_GWYLLGI'              # geometry token: the 32x32 quadruped wait row
CH04_MOOSE_MOV_TABLE = 'TerrainTable_MovCost_AnimalT2Normal'   # the Gwyllgi's own cost row
# Scripted NEUTRALS carrying custom map art (see _inject_scripted_neutral_sprites): units that
# stand on a map wearing our own sprite without being cast members, so classed_cast never sees
# them. (campaign asset id, raw charId, donor base for the wait-row GEOMETRY only).
SCRIPTED_NEUTRAL_SPRITES = (
    ('white-moose', CH04_MOOSE_PID, 'Gwyllgi'),
)
# Where the party first SEES it: the mid-map clearing, on the tomb-side (NE) half of the 15x15
# map. Its authored YAML route then crosses the east bridge and exits to the southeast.
CH04_MOOSE_POS = (11, 4)
CH04_MOOSE_AREA = (9, 2, 14, 7)                 # AREA(x1, y1, x2, y2) -- the clearing it watches from.
                                                # Starts at x=9, NOT x=8: (8,2) is the village
                                                # doorstep (#205), and an AREA covering it fires the
                                                # sighting the moment a unit steps up to visit.
                                                # Vanilla's own AREA (0,9)-(14,14) touched neither
                                                # village. Guarded by a test over `villages:`.
# The Lonelywood villages (#205, #24). Vanilla Ch4 wires TWO -- `Village(0, EventScr_089F1BD8,
# 8, 2)`, the Iron Axe, and `Village(0, .., 1, 11)`, its Lute RECRUIT village -- and we keep both
# tiles and the script shape. WHICH village and WHAT it gives are read from the chapter YAML: a
# village's reward and its line are content, and putting them here is the mistake #208 exists to
# undo.
#
# The Marty->Lupin parley took the recruit village's JOB, so for the whole slice (1,11) stood on
# visitable terrain with no Location entry -- FE8 offers Visit off the location event, so the
# player saw a cottage they could not enter (#24). Vanilla's own text there is pure Lute recruit
# dialogue (9B2/9B3/9B4, zero lore), so there was nothing to copy and the line is ours.
#
# Each village needs its OWN script and message slot -- two doors sharing one script show the
# same line at both and run the give-item tail twice. Keyed by the YAML's village `id`, so a
# third village is one row here plus one `villages:` entry.
#
# BACKDROP: both doors play over CH04_OPENING_FOREST_BG, our winterized fogged forest -- the very
# art Pinky's opening beat B stands in. Vanilla's `BG_NORMAL_VILLAGE` is a TEMPERATE GREEN TOWN,
# and during a village visit the backdrop is the entire screen, so ch04 was showing summer in a
# snowbound fog chapter (Nicolas, 2026-08-05). It is the forest and not our snow-TOWN art
# (BG_MS_TARGOS_WINTER) because there is no town on this map: both cottages are cabins standing
# in the woods, and a visitor is outside one of them -- "if we're outside their cabin, just use
# the bg you put behind pinky in his fog scene".
CH04_VILLAGE_SLOTS = {
    #  id                 event script          msg     mug                  backdrop
    'lonelywood':     ('EventScr_089F231C', 0x9C3, CH04_NIMSY_FID, CH04_OPENING_FOREST_BG),
    # The cottage's logger wears FID_VillagerMan3 -- the mug vanilla itself puts on the snag
    # village (MSG_9B5). It is free for us because our axe village reassigned that door to Nimsy.
    'forest-cottage': ('EventScr_089F2170', 0x9C6, '[FID_VillagerMan3]', CH04_OPENING_FOREST_BG),
}
# `EventScr_089F231C` is a dead Ch5 script (verified free at HEAD). `EventScr_089F2170` is vanilla
# Ch5's OWN village script -- `Village(EVFLAG_TMP(8), .., 12, 10)` in ch5-eventinfo.h, its only
# reference, and inject_ch04 replaces that whole Location list: a village script for a village.
# 0x9C6 is the next free id in ch04's block (it hosts on slot 5, so it owns 0x9BA-0x9CC). ch05's
# YAML labels beats "vanilla 0x9C6" -- those are ANATOMY references mined from its twin, not ids
# it may claim; it will host on its own slot and take that block.
CH04_VILLAGE_SCRIPT, CH04_VILLAGE_MSG = CH04_VILLAGE_SLOTS['lonelywood'][:2]
CH04_COTTAGE_SCRIPT, CH04_COTTAGE_MSG = CH04_VILLAGE_SLOTS['forest-cottage'][:2]
# The snag (#214) -- the Iron Axe's whole purpose. Vanilla Ch4's item village hands the axe over
# to chop this into a bridge, and the retile kept the geometry: (4,8) is the snag, (4,9) the river
# it falls across, (4,10) the far bank. Snags are natively attackable (bmtrick.c auto-adds a 20 HP
# TRAP_OBSTACLE on every TERRAIN_SNAG tile); what needs authoring is the MapChange that
# UpdateObstacleFromBattle applies when it breaks. Region + tile ROLES copied from vanilla's own
# Ch4MapChanges id 1 -- plains / BRIDGE_SNAG / plains -- resolved to snowy-bern metatiles at build
# time so a re-retile cannot leave a stale tile number here.
CH04_SNAG_POS = (4, 8)
CH04_SNAG_SIZE = (1, 3)
# snowy-bern now paints vanilla Ch4's complete 7 / 4 / 11 downed-log composition into its
# matching free slots 7 / 36 / 11: snowy plains with trunk fragments, the felled trunk over
# river water, then snowy plains again. Each preference is still validated against its TERRAIN
# before use -- the art names the slot; the terrain remains the mechanical contract.
CH04_SNAG_TERRAIN = ('TERRAIN_PLAINS', 'TERRAIN_BRIDGE_SNAG', 'TERRAIN_PLAINS')
CH04_SNAG_TILES = (7, 36, 11)
# ch04's goal strings (#207). Its goal donor is ch02's HOST slot, which inject_ch02 has already
# rewritten by the time inject_ch04 runs -- so ch04 inherited ch02's window AND status ids and the
# two wrote over each other (last injector wins; they happened to agree, which is why nothing
# looked broken). These come out of ch04's own dead Ch5 block instead.
CH04_GOAL_WINDOW_MSG = 0x9C4                    # dead Ch5 text slot -> the on-map goal banner
CH04_GOAL_STATUS_MSG = 0x9C5                    # dead Ch5 text slot -> the Status-screen objective
# The EDGE tile it escapes off. Direction is AWAY FROM THE PARTY, who deploy on the NW flank --
# Nicolas 2026-07-31: "I don't care about the direction, I want it to be away from the party; the
# southeast corner makes most sense." So the quarry breaks for the far corner and is gone.
# It was (14, 0) -- the literal NE corner -- and that SOFT-LOCKED the chapter: the corner is
# TERRAIN_PLAINS but a wall of TERRAIN_CLIFF seals the whole NE pocket off from the clearing, so
# the MOVE waited forever on a path that cannot be walked. assert_scripted_move_reachable now
# fails the BUILD on any such destination, and it passes on this one.
# ── ch05 "The Elven Tomb" (#25) ─────────────────────────────────────────────────
# THE TWO OFFSETS, stated once, here, so no other line in inject_ch05 has to know them.
#
#   OURS:     chapter N is hosted on slot N+1. The prologue occupies a real chapter slot
#             (slot 0 has special engine paths that break a stripped chapter -- see
#             inject/hosts.py) and is not numbered, so every chapter sits one slot right of
#             its number. It cannot be renumbered away; it is a consequence of having a
#             prologue at all. The player never sees it: the prep header reads "Chapter 5"
#             off prepScreenNumber (= chapter_number * 2) and the title card is one we draw.
#
#   FE8'S:    vanilla inserted chapter 5X at slot 5, so from slot 6 on the slot INDEX and the
#             vanilla symbol NAME disagree in the BASE GAME -- slot 6 ships Ch5EventData,
#             slot 7 ships Ch6Events. This is the one that reads like a bug and is not ours.
#
# ch05 is a 1:1 retile of vanilla Ch5 and mines Ch5 for everything that is CONTENT -- the
# geometry, the terrain, all sixteen line placements (Ch5's REDA destinations), the nine
# player start tiles, the three east-edge reinforcement waves, the villages, the armory, the
# vendor, the arena, Joshua's tile for Sahnar. None of that is affected by which slot stores
# it. What it takes from the HOST SLOT is storage and nothing else, and since #25 our rosters
# no longer squat on the slot's vanilla tables at all (declare_unit_table) -- so the only
# vanilla names left below are the event lists chapter_settings.json points at structurally.
# CH05_HOST_INDEX (6) / CH05_EVENT_GROUP ('Ch6Events' -- FE8's offset, not ours): inject/hosts.py.
CH05_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch6-eventinfo.h')
CH05_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch6-eventscript.h')
# The host slot's event-list symbols. These CANNOT be renamed -- the ChapterEventGroup that
# chapter_settings.json resolves is built from them -- so they are named here and nowhere else.
CH05_EVENT_LISTS = {
    'turn': 'EventListScr_Ch6_Turn',
    'character': 'EventListScr_Ch6_Character',
    'location': 'EventListScr_Ch6_Location',
    'misc': 'EventListScr_Ch6_Misc',
    'select_unit': 'EventListScr_Ch6_SelectUnit',
    'select_dest': 'EventListScr_Ch6_SelectDestination',
    'unit_move': 'EventListScr_Ch6_UnitMove',
    'tutorial': 'EventListScr_Ch6_Tutorial',
}
CH05_BEGINNING_SCRIPT = 'EventScr_Ch6_BeginningScene'
CH05_ENDING_SCRIPT = 'EventScr_Ch6_EndingScene'
# Dead host-slot scripts repurposed for our reinforcement waves. Unreachable once the event
# lists above are stripped; each verified free by grep (the ch03/ch04 idiom).
CH05_WAVE_SCRIPTS = {2: 'EventScr_089F2B74', 3: 'EventScr_089F2940', 5: 'EventScr_089F2A98'}
CH05_PREP_SCRIPT = 'EventScr_08591FD8'           # the shared CLEAN/PREP/CLEAN script (cf. ch03/ch04)

# Our OWN roster tables (declare_unit_table). Named for the chapter whose units are in them.
CH05_ALLY_TABLE = 'MS_Ch05DeployCap'             # the never-LOADed PREP cap template
CH05_BOOT_SEED_TABLE = 'MS_Ch05BootSeed'         # --ch05-boot only: an armed party from a cold start
CH05_LINE_TABLE = 'MS_Ch05Line'                  # the 16 turn-1 tomb-guardians
CH05_SAHNAR_TABLE = 'MS_Ch05Sahnar'              # the turn-2 convertible (rises hostile)
CH05_BASIL_TABLE = 'MS_Ch05Basil'                # Basil, GREEN at the pocket mouth (see below)
CH05_WAVE_TABLES = {2: 'MS_Ch05Wave2', 3: 'MS_Ch05Wave3', 5: 'MS_Ch05Wave5'}

# ── The two-stage ch05 recruit (#25): Basil joins in the OPENING, then Talks Sahnar ──────
# Vanilla Ch5's Character list is exactly ONE entry -- CHAR(EVFLAG_TMP(7), ..., NATASHA, JOSHUA)
# -- because its escort is already a party member (Natasha is BLUE in UnitDef_Event_Ch5Ally) and
# only the DUELIST needs talking down. Ours is the same single entry, and Basil reaches the same
# state by a different road: she is recruited IN this chapter, so she cannot ride the prep
# roster (_classed_cast(available_at=5) excludes her). She is LOADed GREEN instead and CUSA'd
# BLUE by the opening's own join beat -- basil.md Q3, and the locked 0x9C2 ("...I wonder.
# Sahnar. ...She needs me. Take me to her?"), whose trigger is chapter_start, NOT a Talk.
# So: no CHAR entry for Basil. One CHAR entry, Basil -> Sahnar, exactly like the twin.
CH05_BASIL_MOV_TABLE = 'TerrainTable_MovCost_MagicNormal'   # Cleric's own cost row (data_classes.c)
CH05_BASIL_GREEN_POS = (5, 15)   # the row-15 corridor at the deploy pocket's mouth. NOT one of
                                 # the nine deploy_slots (rows 16-19) -- those are the party's
                                 # and PREP fills all nine, so standing on one would cost a
                                 # deployment. Row 15 is open end-to-end and the four stairs are
                                 # at x=1/3/9/10, so she blocks no exit. Verified walkable and
                                 # connected to Sahnar's tile by assert_green_recruit_placement.
# The join beat is SILENT, and that is a constraint rather than a choice. ch05's YAML labels its
# scenes `slot: "vanilla 0x9C2"` and the like, but those labels are ANATOMY REFERENCES to the
# chapter we MINE (vanilla Ch5) -- they are not ids we may write, because ch04 hosts on slot 5 and
# owns that whole block (HOSTED_CHAPTER_MESSAGE_IDS['ch04'] = 0x9BA..0x9C6). 0x9C2 in the built
# ROM is ch04's OWN no-parley ending (CH04_ENDING_NO_LUPIN_MSG), so pointing Basil's join at it
# plays Pinky and Marty discussing supper. Reading an UNWRITTEN vanilla id as a placeholder is
# fine and we do it (the reliquary visits, and the Talk below); reading one another chapter
# WRITES is not -- that distinction is the whole reason the registry exists.
# OWED: the dialogue pass gives this beat an id from ch05's own block (vanilla Ch6, 0x9E4..0x9F5)
# and registers it. Until then the shrub joins wordlessly -- the WIRING is what ships here.
CH05_SAHNAR_TALK_SCRIPT = 'MS_Ch05SahnarTalk'   # ours (declare_event_script), not a squatted
                                                # vanilla symbol -- campaign-owned event scripts,
                                                # declared AFTER the block-replacement pass.
CH05_SAHNAR_TALK_MSG = 0x9CC     # the TALK-RECRUIT scene. UNCLAIMED by every chapter (checked
                                 # against HOSTED_CHAPTER_MESSAGE_IDS), so the ROM still holds
                                 # vanilla's text -- which is vanilla's OWN Natasha->Joshua talk
                                 # recruit, the exact scene ours is the twin of. The reliquary
                                 # placeholder pattern (decisions.md "Vanilla prose is a
                                 # legitimate PLACEHOLDER"). The dialogue pass must MOVE this to
                                 # ch05's block, not overwrite 0x9CC -- it is ch04's neighbourhood.
CH05_SAHNAR_TALK_FLAG = 'EVFLAG_TMP(7)'   # vanilla Ch5's own Natasha->Joshua CHAR flag, free
                                          # here: ch05's villages take eid 0 and its Misc list
                                          # is DefeatBoss + CauseGameOverIfLordDies only.

# The four reliquary visits. Each rides OUR OWN script (declare_event_script) but shows VANILLA
# Ch5's own village line, by pointing at the message id that already holds it -- we never WRITE
# 0x9CD..0x9D0, so the ROM keeps vanilla's text verbatim and the id stays unclaimed
# (HOSTED_CHAPTER_MESSAGE_IDS). ch05's authored dialogue skips this range exactly (it runs
# 0x9BE..0x9CC then jumps to 0x9D5), so nothing collides.
#
# WRITTEN 2026-08-08 (dialogue-pass): the four bodies are ours now, at these same ids, and the
# ids are CLAIMED in HOSTED_CHAPTER_MESSAGE_IDS. Writing outside ch05's own host block is
# deliberate and safe, which is worth stating because the registry's whole point is that it
# usually is NOT: 0x9CD..0x9D0 are vanilla Ch5's village lines, and the only scripts that ever
# displayed them are `EventScr_089F2170` (which inject_ch04 REPLACES for its forest cottage) and
# `EventScr_089F21BC`/`21F8`/`2234` (left in ch5-eventscript.h but unreferenced once inject_ch04
# rewrites Ch5's Location list -- dead code, never run). Verified against HEAD, not assumed.
# The alternative -- spending four of ch05's own 16-id block -- was rejected because the
# remaining cutscene pass (#25) needs that block and HANDOFF already prices it as tight.
CH05_VILLAGE_SLOTS = {
    #  id                  event script          msg     mug
    'reliquary-east':  ('MS_Ch05VisitEast',  0x9CD, '[FID_VillagerMan1]'),
    'reliquary-south': ('MS_Ch05VisitSouth', 0x9CE, '[FID_VillagerMan2]'),
    'reliquary-west':  ('MS_Ch05VisitWest',  0x9CF, '[FID_VillagerYoungMan]'),
    'reliquary-north': ('MS_Ch05VisitNorth', 0x9D0, '[FID_ManUnused]'),
}
# The event id each site sets when the party gets there first -- the whole race, in four flags
# (#25). It records the visit, disarms that site's raider hook (Village() puts the same eid on
# the destruction LOCA), and answers the save-all CHECK_EVENTID at the ending.
#
# NOT vanilla Ch5's own 8..11, and that is the one number here worth reading twice: ch05's
# opening ends on ENUT(8) -- `ENUT` is EvtSetFlag (EAstdlib), a vanilla prep-chapter idiom
# (ch12a, ch18a), NOT an un-trigger -- and CH05_SAHNAR_TALK_FLAG holds 7. A site on either would
# begin the chapter already flagged: unvisitable, unraidable, and counted toward a payout the
# player never earned. Flags 7-40 are free (event-flags.h), so ch05's four start after 8.
CH05_VILLAGE_FLAGS = {
    'reliquary-east':  'EVFLAG_TMP(9)',
    'reliquary-south': 'EVFLAG_TMP(10)',
    'reliquary-west':  'EVFLAG_TMP(11)',
    'reliquary-north': 'EVFLAG_TMP(12)',
}
# Top-left metatile of the tileset's DRAWN 3x2 ruined structure (740..742 / 772..774), which is
# what a desecrated reliquary becomes. Named rather than searched because it is a picture, not a
# terrain -- see _drawn_block, which verifies every cell of it at build time.
CH05_RUIN_ORIGIN = 740
# A village visit paints the backdrop over the WHOLE screen, so this is not set dressing -- it is
# where the scene appears to happen. Vanilla Ch5's villages use BG_HOUSE, and inheriting it put a
# warm human cottage (lit hearth, cooking pot) behind a skeleton in a frozen elven tomb. Same
# defect ch04 shipped and fixed (a summer forest in a snowbound fog chapter, Nicolas 2026-08-05):
# a retile inherits the twin's BACKDROP too, and the twin's backdrop is about the twin's setting.
CH05_VISIT_BG = 'BG_INTERIOR_BROWN'  # Nicolas's pick 2026-08-09, chosen off an in-engine
                                    # four-way (stone chamber / house / interior brown /
                                    # black temple): the map draws these sites as BUILDINGS,
                                    # so the interior should read as somewhere you stepped
                                    # INTO. BG_HOUSE's lit hearth and cooking pot are a
                                    # kitchen; the black temple is draped in green vines,
                                    # wrong for two years of unbroken winter.
# The four residents' BUSTS. The sites are a TOMB, so the speakers are the tomb's own risen dead
# (Nicolas, 2026-08-08) and every one needs a face FE8 does not ship -- there is no undead mug in
# the base ROM (checked the whole FID table; the closest is a plain villager).
#
# SLOT CHOICE: each rides a vanilla portrait slot that is collision-free -- absent from our
# ch00-08 and dressed by nothing else in this file. Villager_Man_3/4, Old_Man, Old_Woman,
# Young_Boy and Woman are all SPOKEN FOR (ch02's fisher, ch03's crier, ch04's Nimsy and logger,
# a prologue guest), so the free ones are Man_1, Man_2, Young_Man and the literally-unused
# Man_Unused. Overwriting a slot's graphics is GLOBAL, so "free" has to mean free everywhere.
#
# DERIVED AT BUILD TIME from the vendored FE-Repo mug, the chwinga pattern -- no committed
# derived asset, so the vendored PNG stays the single source. The two skeletons in orange
# pauldrons are the SAME BODY with a different jaw, so the south one is recoloured verdigris or
# the player meets the same man twice; only the two true oranges move, because the third tone in
# that ramp is also the SKULL's shadow (y 10..72, vs the pauldrons' y>=52) and recolouring it
# turns his teeth green.
CH05_VISIT_ORANGE_TO_VERDIGRIS = {(192, 96, 48): (86, 138, 116), (136, 80, 56): (52, 92, 80)}
CH05_VISIT_FACES = {
    #  id                 vendored FE-Repo mug                                    slot            recolor
    'reliquary-north': ('Cantor {Eden, L95} [F2E].png',                     'Man_Unused',        None),
    'reliquary-west':  ('Skeleton (Mage, version 1) {L95, BladerDj} [F2E].png',
                                                                            'Villager_Young_Man', None),
    'reliquary-east':  ('Skeleton {L95} [F2E].png',                         'Villager_Man_1',    None),
    'reliquary-south': ('Skeleton (Full Smile) {L95, Nokitrix} [F2E].png',   'Villager_Man_2',
                        CH05_VISIT_ORANGE_TO_VERDIGRIS),
}
# The elven store (`economy.elven_store`). Armory/Vendor take their stock DIRECTLY -- no script,
# no text -- so these are wired PERMANENTLY, not as placeholders. Stock is vanilla Ch5's own,
# which is what `make difficulty CH=ch05` prices the shop tier against.
CH05_SHOPS = (('Armory', 'ShopList_Event_Ch5Armory', 2, 1),
              ('Vendor', 'ShopList_Event_Ch5Vendor', 6, 10))

CH05_LAYOUT = ('Ch05ElvenTombMap', 'ch05-the-elven-tomb')   # (asset label, maps/ stem)
CH05_CHAPTER_YAML = 'ch05-the-elven-tomb.yaml'
CH05_TILESET = 'port-or-town-winter'             # stem 'PortTown'; ch05 is the first chapter to
                                                 # use it, so it self-registers (the Cave idiom)
CH05_GOAL_DONOR = 7                              # vanilla slot 7 = a clean defeat_boss template.
                                                 # NOT slot 6: that is ch05's own host slot, so
                                                 # donating from it would copy a goal the chapter
                                                 # is in the middle of replacing.
# ch05's goal strings come from its HOST SLOT's dead block (vanilla Ch6 = 0x9E4..0x9F5), not
# from vanilla Ch5's -- ch04 hosts on slot 5 and already owns that block (#207).
CH05_ERUPTION_MSG = 0x9E4                     # turn-2 Ravisin warning; first free Ch6-host id
CH05_GOAL_WINDOW_MSG = 0x9F4
CH05_GOAL_STATUS_MSG = 0x9F5
# Raw charIndexes. Pids need only be unique WITHIN a chapter -- gDefeatTalkList entries carry
# .chapter, so ch03's 0xb7 and ch04's 0xb7 coexist -- but the boss and the moose need their own
# so their flagged death entries key to them alone.
CH05_BOSS_PID = '0xb8'                           # Ravisin: flagged EVFLAG_DEFEAT_BOSS -> the WIN
CH05_MOOSE_PID = '0xb9'                          # the white moose: named, but NOT the win condition
CH05_SAHNAR_PID = '0xba'                         # Sahnar: her own pid so Basil's Talk can address
                                                 # HER and not the nearest identical myrmidon
                                                 # (#203's lesson). Becomes her CHARACTER_ slot
                                                 # when the recruit pass gives her one (#25).
CH05_GENERIC_PID = '0x80'                        # autolevelled trash (vanilla Ch6's own generic)
# Raw CharacterData identity binding. Riev contributes collision-free name/portrait slots:
# MSG_246 is retitled Ravisin and portrait id 0x48 is dressed from ravisin.png.
RAW_PID_PORTRAITS = {
    CH05_BOSS_PID: ('ravisin', GUEST_PORTRAIT_MAP['ravisin'], 0x48, 'Ravisin'),
}
# The chapter YAML is the authority for named raw-pid boss bases. These values cannot flow
# through patch_character_data(), which only visits the regular CHARACTER_* portrait map.
RAW_PID_PERSONAL_SOURCES = {
    CH05_BOSS_PID: (CH05_CHAPTER_YAML, 'ravisin'),
}
CH05_AI = {
    'aggressive': '{0x0, 0x0, 0x1, 0x0}',        # pursue/charge
    'defensive': '{0x3, 0x3, 0x9, 0x20}',        # hold and strike in range
    'hold_position': '{GuardTileAI, 0x9, 0x20}', # vanilla Saar's boss posture
    # AI_B_04 = AiScr_AiB_PillageThenPursue (cp_data.c): head for the nearest lootable tile,
    # sack it, then fight normally. Vanilla Ch5 puts this on all six of its reinforcements and
    # nothing else, which is the whole village-raid race -- the AI is terrain-driven
    # (gTerrainList_LootableVillages), so it needs no target list and no class of its own.
    'raider': '{0x0, 0x4, 0x9, 0x0}',
}
CH05_CLASS_IDS = {'druid': 'CLASS_DRUID', 'gwyllgi': 'CLASS_GWYLLGI',
                  'soldier': 'CLASS_SOLDIER', 'fighter': 'CLASS_FIGHTER',
                  'mercenary': 'CLASS_MERCENARY', 'archer': 'CLASS_ARCHER',
                  'myrmidon': 'CLASS_MYRMIDON'}
CH05_ITEM_IDS = {'flux': 'ITEM_DARK_FLUX', 'rotten-claw': 'ITEM_MONSTER_ROTTENCLW',
                 'iron-lance': 'ITEM_LANCE_IRON', 'iron-axe': 'ITEM_AXE_IRON',
                 'iron-sword': 'ITEM_SWORD_IRON', 'iron-bow': 'ITEM_BOW_IRON',
                 # FE8 calls the Killing Edge ITEM_SWORD_KILLER -- it is the sword vanilla
                 # Joshua carries on this very map, and Sahnar is his 1:1 (crit-threat duelist)
                 'killing-edge': 'ITEM_SWORD_KILLER',
                 # the four reliquary gifts (villages) -- vanilla Ch5's own reward tier, and
                 # the exact items `make difficulty CH=ch05` prices the economy against
                 'booster-def': 'ITEM_BOOSTER_DEF', 'booster-skl': 'ITEM_BOOSTER_SKL',
                 'armorslayer': 'ITEM_SWORD_ARMORSLAYER', 'torch': 'ITEM_TORCH',
                 # the save-all-four bonus -- vanilla Ch5's own, handed over at the ending
                 'guiding-ring': 'ITEM_GUIDINGRING'}


# ── Message-id ownership across hosted chapters (#198 review, issue #24) ────────
# Each hosted chapter writes text into DEAD message slots belonging to the vanilla chapter it
# hosts ON -- ch03 sits on slot 4 and takes vanilla Ch4's block, ch04 sits on slot 5 and takes
# vanilla Ch5's. Two chapters claiming one id is a SILENT failure: `verify_text` decodes what
# it finds and checks for runaway text, not for who owns a slot, so the second writer simply
# overwrites the first and the build stays green.
#
# That is not hypothetical. ch05's YAML labels its beats `slot: "vanilla 0x9BB"` / `"0x9BC"`,
# which are ANATOMY references mined from its FE8 twin -- but the same field means a LITERAL id
# a few lines away (`"vanilla 0x9C6" # data_battlequotes.c, pid CHARACTER_NATASHA`), and ch04
# writes real text into 0x9BB/0x9BC right now. ch05's text insertion is still owed (#25), so
# this guard lands FIRST, deliberately.
HOSTED_CHAPTER_MESSAGE_IDS = {
    'ch03': (CH03_BOSS_DEATH_MSG,        # reserved: the grell's quote was CUT (msg=0) but the
                                         # slot stays ch03's, so nothing else may take it
             CH03_TREX_TALK_MSG, CH03_OPENING_CARD_MSG, *CH03_OPENING_MSGS,
             CH03_ENDING_CARD_MSG, *CH03_ENDING_MSGS, CH03_TREX_ENTRANCE_MSG,
             *CH03_MIDMAP_MSGS, CH03_GOAL_WINDOW_MSG, CH03_GOAL_STATUS_MSG),
    'ch04': (CH04_LUPIN_TALK_MSG, *CH04_REVEAL_MSGS, CH04_OPENING_CARD_MSG,
             *CH04_OPENING_MSGS, CH04_MOOSE_MSG, CH04_ENDING_MSG,
             CH04_ENDING_NO_LUPIN_MSG, CH04_VILLAGE_MSG, CH04_COTTAGE_MSG,
             CH04_GOAL_WINDOW_MSG, CH04_GOAL_STATUS_MSG),
    # ch05 hosts on slot 6, so it takes vanilla CH6's dead block (0x9E4..0x9F5) -- NOT vanilla
    # Ch5's, even though ch05 is vanilla Ch5's 1:1 twin in every other respect. ch04 sits on
    # slot 5 and already owns that block. This is the sharpest case of the two offsets: the
    # chapter we MINE and the block we WRITE INTO are different vanilla chapters, and the
    # YAML's `slot: "vanilla 0x9BB"` labels are anatomy references to the mined chapter, not
    # claims on ids. The eruption warning is the first dialogue claim from that block; later
    # cutscene ids land with the remaining dialogue pass (#25), and this guard will refuse them
    # if any collide.
    # The four reliquary visit lines joined the block 2026-08-08 (dialogue-pass). They sit
    # OUTSIDE ch05's host block on purpose -- see CH05_VILLAGE_SLOTS for why that is safe here
    # and why spending ch05's own ids on them was the worse trade.
    'ch05': (CH05_ERUPTION_MSG, CH05_GOAL_WINDOW_MSG, CH05_GOAL_STATUS_MSG,
             *(slot[1] for slot in CH05_VILLAGE_SLOTS.values())),
    # Goal ids only -- ch01/ch02 predate the per-chapter block registry, but their goal strings
    # still have to be unique against every other hosted chapter (#207).
    'ch01': (CH01_GOAL_WINDOW_MSG, CH01_GOAL_STATUS_MSG),
    'ch02': (CH02_GOAL_WINDOW_MSG, CH02_GOAL_STATUS_MSG),
}


def assert_message_ids_unique(claims=None):
    """Guard: no two hosted chapters may claim the same message id.

    Called from main() before any injector runs, so a collision fails the BUILD rather than
    shipping a chapter whose text was quietly overwritten by the next one. Add a chapter's
    block to HOSTED_CHAPTER_MESSAGE_IDS when it starts hosting -- that registry is the
    declaration of ownership, and this is what makes it binding.
    """
    owner = {}
    for chapter, ids in sorted((claims if claims is not None
                                else HOSTED_CHAPTER_MESSAGE_IDS).items()):
        for mid in ids:
            if mid in owner:
                sys.exit('ERROR: message id 0x%X is claimed by BOTH %s and %s. Hosted '
                         'chapters take their host slot\'s dead message block -- pick ids '
                         'from the block %s actually owns (see HOSTED_CHAPTER_MESSAGE_IDS).'
                         % (mid, owner[mid], chapter, chapter))
            owner[mid] = chapter
    return owner


def assert_message_id_unclaimed(msg_id, chapter, what):
    """A chapter may DISPLAY a vanilla message id it does not own -- that is the placeholder
    pattern (decisions.md "Vanilla prose is a legitimate PLACEHOLDER"), and ch05's reliquary
    visits and Sahnar Talk both do it. What it may NOT do is display an id ANOTHER hosted
    chapter WRITES: the player then gets that chapter's scene, in its voice, with its faces.

    The two cases are indistinguishable at the call site -- both are an int in a constant -- so
    the difference has to be checked rather than remembered. It is an easy mistake to make from
    the chapter YAML alone, because our scene labels (`slot: "vanilla 0x9C2"`) name the chapter
    we MINE, not the block we may write into, and for a chapter hosted on a shifted slot those
    are different vanilla chapters entirely.

    Found by review on #25: ch05's Basil join beat pointed at 0x9C2, which is ch04's own
    no-parley ending -- so the shrub's join would have played Pinky and Marty discussing supper.
    """
    holder = assert_message_ids_unique().get(msg_id)   # the registry, already collision-checked
    if holder is not None and holder != chapter:
        sys.exit('ERROR: %s (%s) displays message 0x%X, but %s OWNS and WRITES that id -- the '
                 'scene would play %s\'s text. Placeholder prose must come from an id NO hosted '
                 'chapter writes (see HOSTED_CHAPTER_MESSAGE_IDS).'
                 % (what, chapter, msg_id, holder, holder))


def variant_beat(beat, fallback, err_label):
    """Splice a scene's `no_lupin_fallback`-style variant over its locked beat.

    A chapter YAML declares the fallback as `boxes:` (1-based indices), `replaces:` (the
    OPENING TEXT of each box it stands in for) and a `script:` of the substitute lines --
    one per box, in the same order. The `replaces:` anchors exist so an index cannot
    silently drift: we assert each named box still starts with its anchor before swapping,
    and hard-fail if the locked script has been re-ordered underneath the fallback.

    Returns a new beat, same length as `beat`, with the named boxes replaced and every
    other box (e.g. ch04's Marty box 2, unchanged in both branches) carried through.

    Reused by ch05's five conditional scenes (#25) -- one mechanism, not two.
    """
    boxes, anchors = fallback['boxes'], fallback['replaces']
    subs = fallback['script']
    if not (len(boxes) == len(anchors) == len(subs)):
        sys.exit('ERROR: %s: fallback declares %d boxes, %d replaces, %d script lines '
                 '-- all three must agree' % (err_label, len(boxes), len(anchors), len(subs)))
    out = list(beat)
    for idx, anchor, sub in zip(boxes, anchors, subs):
        if not 1 <= idx <= len(beat):
            sys.exit('ERROR: %s: fallback box %d is outside the %d-box scene'
                     % (err_label, idx, len(beat)))
        (_, text), = beat[idx - 1].items()
        if not _fe_dialogue_text(text).startswith(_fe_dialogue_text(anchor)[:40]):
            sys.exit('ERROR: %s: fallback box %d anchored to %r but that box now reads %r '
                     '-- the locked script moved; re-anchor the fallback'
                     % (err_label, idx, anchor[:40], text[:40]))
        out[idx - 1] = sub
    return out


def branch_on_flag(flag, if_set, if_clear, label_base=0):
    """A vanilla-shaped event branch: run `if_set` when `flag` is set, else `if_clear`.

    The FE8 idiom (cf. ch19a's ending, which picks its text by CHECK_EVENTID + CHECK_ALIVE):
    CHECK_EVENTID leaves the flag in slot C, BEQ jumps when it equals slot 0 (clear), and both
    arms converge on a shared LABEL. `label_base` offsets the two labels so several branches
    can coexist in one script without colliding.
    """
    a, b = label_base, label_base + 1
    return ('    CHECK_EVENTID(%s)\n'
            '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* flag clear -> the fallback arm */\n'
            % (flag, a)
            + if_set
            + '    GOTO(0x%X)\n'
              'LABEL(0x%X)\n' % (b, a)
            + if_clear
            + 'LABEL(0x%X)\n' % b)


def convert_survivors_green(pids, label_base, what):
    """Flip each named unit GREEN where it stands, skipping any that is already dead.

    The group-parley primitive (ch04's wolf pack): one CHECK_ALIVE-guarded CUSN per pid, so
    the conversion is IN PLACE -- no DISA + LOAD1, which would teleport the group back to its
    spawn tiles and resurrect anyone the player had already killed.

    The guard is not optional. `UnitKill` WIPES a non-blue unit's slot (pCharacterData = NULL,
    bmunit.c:988), and `Event34_MessWithUnitState` gives only DISA/KILL the graceful path --
    a CUSN on an unresolvable pid returns EVC_ERROR (eventscr.c:3317). So a bare sweep breaks
    in exactly the kill-then-parley case. CHECK_ALIVE is safe on a wiped slot (eventscr.c:3212:
    missing -> slot C = 0) and is already ch02's per-chwinga idiom.

    Falling out of that: the ally count SCALES WITH SURVIVORS for free -- CUSN can only convert
    what still exists, so killing two wolves before talking costs you two allies (#203).
    `label_base` offsets the per-unit skip labels so several sweeps can share one script.
    """
    return ''.join(
        '    CHECK_ALIVE(%s)\n'
        '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* %s %d/%d already dead -> nothing to convert */\n'
        '    CUSN(%s) /* -> green, where it stands */\n'
        'LABEL(0x%X)\n'
        % (pid, label_base + i, what, i + 1, len(pids), pid, label_base + i)
        for i, pid in enumerate(pids))


def village_script(msg, item, bg):
    """A village visit, in vanilla Ch4's own shape (EventScr_089F1BD8): one text box over the
    village BG, then the reward into the visitor's hands.

    `SVAL(EVT_SLOT_3, item)` + `GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)` is the engine's give-an-item
    idiom -- slot 3 carries the item id and the ACTIVE unit is the one who walked in, so the axe
    lands on the visitor (overflowing to the convoy if their pack is full), not on a fixed pid.

    `item` is None for a village whose reward IS its line -- ch04's economy is deliberately
    Ch4-lean (decisions.md: one Iron Axe, no gold, no chests), so the forest cottage pays in
    lore. That drops vanilla's give-item tail rather than handing over some default; the
    EVBIT_T(7) visit flag stays either way, or the door never shuts behind you.
    """
    give = ('' if item is None else
            '    SVAL(EVT_SLOT_3, %s)\n'
            '    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n' % item)
    return ('{\n'
            '    MUSI\n'
            '    Text_BG(%s, 0x%X)\n'
            '    MUNO\n'
            '    CALL(EventScr_RemoveBGIfNeeded)\n'
            '%s'
            '    EVBIT_T(7)\n'
            '    ENDA\n}' % (bg, msg, give))


def village_reward_id(village):
    """The YAML id of what a village hands over, or None when its reward is the line alone."""
    reward = village.get('visit_reward')
    return reward[0]['id'] if reward else None


def village_reward_item(village, item_ids):
    """The FE item enum a village hands over, or None when its reward is the line alone.

    `item_ids` is the CHAPTER's id->enum map. It used to close over CH04_ITEM_IDS, which made a
    shared helper silently ch04-only: ch05's gifts (the two stat boosters) are not in that dict,
    so the first chapter to reuse it would have died on a KeyError naming ch04.
    """
    reward = village_reward_id(village)
    return item_ids[reward] if reward else None


def village_boxes(village):
    """A village's line, as the GBA boxes it was AUTHORED in -- one `visit_text` entry per
    A-press.

    Village text is dialogue, so its buttons belong on its beats. Flowed as a single scalar it
    reflows wherever the 42-column wrap lands and buttons mid-sentence: the axe village's
    "vanilla 1:1" text came out as THREE boxes breaking on "a handy bridge if / you could knock
    it over", where vanilla's own MSG_9B5 is FOUR broken on its sentences -- 1:1 in words but
    not on screen, which is not what 1:1 meant (Nicolas, 2026-08-02). A flowed scalar is
    therefore rejected outright rather than silently reflowed.
    """
    text = village.get('visit_text')
    if isinstance(text, str) or not text:
        sys.exit('ERROR: village %r must author `visit_text` as a LIST -- one entry per GBA '
                 'box. A flowed scalar reflows at the wrap width and puts the A-press breaks '
                 'mid-sentence.' % village['id'])
    return [' '.join(box.split()) for box in text]


def location_events(villages, village_slots, shops=(), flags=None):
    """The host slot's Location list: everything the player can VISIT.

    One `Village` per authored village, at the tile the chapter YAML names, each running its OWN
    script (`village_slots[id]`) -- two doors sharing one script show the same line at both.

    `Village(eid, scr, x, y)` expands to VILL + a LOCA on the tile ABOVE (EAstdlib) carrying
    TILE_COMMAND_20 -- and that second entry is the DESTRUCTION hook: a raider that reaches the
    door runs AiPillageAction, which calls StartAvailableTileEvent(x, y - 1) (cp_perform.c) and
    flips the tile through the chapter's MapChange array. Both entries carry the same `eid`.

    `flags` is {village id: event-flag expression} -- the id FE8 sets when the site is visited.
    It defaults to 0, which is EVFLAG_ALWAYS_FALSE: CheckChapterFlag(0) returns 0 forever
    (eventinfo.c), so SearchAvailableEvent never skips a 0 entry. A chapter that only needs
    doors can leave it alone; a chapter that RACES for its sites cannot, because the same flag
    is what records the visit, disarms that site's raider hook, and answers the save-all
    CHECK_EVENTID at the ending (#25).

    `shops` are `(macro, shoplist_symbol, x, y)` -- `Armory`/`Vendor` take their stock DIRECTLY
    and run no script and show no text, so a shop is fully wired the moment its tile is listed.

    **An empty Location list makes every reward on the map unobtainable while the map still draws
    it.** That is how ch04 shipped an unreachable Iron Axe (#205), and it is why this returns a
    list built from the YAML rather than something a chapter has to remember to fill in.
    """
    flags = flags or {}
    rows = ''.join(
        '    Village(%s, %s, %d, %d) /* %s -- %s */\n'
        % (flags.get(v['id'], '0'), village_slots[v['id']], v['tile'][0], v['tile'][1],
           v['id'], village_reward_id(v) or 'the line is the reward')
        for v in villages)
    rows += ''.join('    %s(%s, %d, %d)\n' % shop for shop in shops)
    return '{\n' + rows + '    END_MAIN\n}'


def ch04_location_events(chap):
    """ch04's Location list. Vanilla Ch4 wires two villages and so do we (#24); no shops."""
    return location_events(chap.get('villages', []),
                           {vid: slot[0] for vid, slot in CH04_VILLAGE_SLOTS.items()})


METATILES_PER_ROW = 32          # tileset atlas stride, for reading a drawn multi-tile block


def _drawn_block(tileset, origin, size, terrain_name, what):
    """The `size`-shaped run of metatiles starting at `origin`, checked to be real art of the
    right terrain -- for a map change that must draw a STRUCTURE rather than a repeated tile.

    `_snowy_metatile_for` resolves one terrain to one metatile, which is all a door or a bridge
    needs. A ruined building is a picture: six adjacent metatiles the tileset artist drew to fit
    together, and picking "the lowest painted ruins tile" six times would tile one corner across
    the whole footprint. So the origin is named, and then VERIFIED -- every cell must carry
    `terrain_name` and be painted, which is what turns a renumbered tileset into a loud build
    failure instead of a silently wrong picture (#205's lesson, kept)."""
    want = terrain_ids()[terrain_name]
    width, height = size
    tiles = [origin + row * METATILES_PER_ROW + col
             for row in range(height) for col in range(width)]
    for m in tiles:
        if tileset.terrain(m) != want:
            sys.exit('ERROR: %s expects %s across %dx%d from metatile %d, but %d carries '
                     'terrain 0x%02x -- the tileset was renumbered, so re-pick the origin'
                     % (what, terrain_name, width, height, origin, m, tileset.terrain(m)))
        if _is_blank_metatile(tileset, m):
            sys.exit('ERROR: %s writes blank metatile %d (a declared-but-unpainted tile renders '
                     'as a solid block)' % (what, m))
    return tiles


SAVE_ALL_SKIP_LABEL = '0x2'     # vanilla Ch5's own label for "a site was lost -- skip the gift"


def save_all_bonus_script(flags, item):
    """Vanilla's save-all-the-villages payout (`EventScr_Ch5_EndingScene`), as event lines.

    One CHECK_EVENTID per site, each branching PAST the gift the moment its flag reads unset --
    so the reward survives only a clean sweep, and any single lost site skips the lot. The
    flags are the ones the Location list armed; a site that was raided never set its id, and
    neither did one the player simply walked past.

    CHAR_EVT_PLAYER_LEADER, not the village idiom's CHAR_EVT_ACTIVE_UNIT: nobody is standing on
    a tile at the ending, so there is no active unit for the item to land on."""
    lines = []
    for flag in flags.values():
        lines += ['    CHECK_EVENTID(%s)' % flag,
                  '    BEQ(%s, EVT_SLOT_C, EVT_SLOT_0)' % SAVE_ALL_SKIP_LABEL]
    lines += ['    SVAL(EVT_SLOT_3, %s)' % item,
              '    GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)',
              'LABEL(%s)' % SAVE_ALL_SKIP_LABEL]
    return '\n'.join(lines) + '\n'


def ch05_ending_script(chap):
    """ch05's ending: the save-all payout, then the win.

    The payout happens inside the ending scene rather than through the Village macro, because
    the condition is "all four" and no single tile knows that. ch06 is not hosted yet, so the
    win still lands on the dev placeholder exactly as ch04's did until ch05 hosted.

    BEFORE the FADI, and that is not cosmetic. Vanilla restores the screen
    (`EventScr_RemoveBGIfNeeded`) immediately ahead of its own `GIVEITEMTO`, and the reason
    shows up on a full pack: the give runs `HandleNewItemGetFromDrop`, which opens a BLOCKING
    convoy/discard menu. Handing the ring over after `FADI(16)` puts both the item popup and
    that menu behind a black screen, leaving the player pressing buttons at nothing.

    The gates come from the CHAPTER's villages, not from the module dict, so the payout can
    only ever check ids the Location list actually armed. Gating on `CH05_VILLAGE_FLAGS`
    wholesale meant that dropping a village from the YAML would leave the ending waiting on a
    flag nothing could set -- an unobtainable reward, with a green build."""
    flags = {v['id']: CH05_VILLAGE_FLAGS[v['id']] for v in chap.get('villages', [])}
    return ('{\n    MUSC(SONG_VICTORY)\n'
            + save_all_bonus_script(flags, CH05_ITEM_IDS[chap['economy']['save_all_bonus']])
            + '    FADI(16)\n'
            + dev_placeholder_scene() + '    ENDA\n}')


def ch05_map_changes(chap, maps_dir):
    """ch05's tile flips: a reliquary DESECRATED, and a reliquary visited (#25).

    Vanilla Ch5's own array, one for one -- four 3x2 ruins at (doorX - 1, doorY - 1) then four
    1x1 doors, and the ORDER is the correctness argument. GetMapChangeIdAt keeps the LAST region
    covering a tile (bmtrick.c) and the 3x2 overlaps its own door, so doors-first would make
    VISITING a site collapse the building.

    The 3x2 footprint is not decoration either. AiPillageAction looks the change up at
    (x, y - 1) -- the tile above the door, where Village()'s destruction LOCA sits -- so a
    change on the door alone is never found and a sacked site would keep standing, keep its
    gift, and keep counting toward the save-all payout.

    RUINS_REGULAR is the lost state and the choice is load-bearing: FE8 decides both "can a unit
    Visit here" (CanUnitVisit, bmmenu.c) and "is this worth pillaging" (gTerrainList_Lootable-
    Villages, cp_utility.c) from the TERRAIN, and RUINS_VILLAGE -- the obvious-sounding pick --
    is in both lists. A site ruined into it would be lootable again the next turn."""
    import map_tileset_tool as mt
    tileset = mt._tileset_from_dir(os.path.join(maps_dir, 'tilesets', CH05_TILESET))
    villages = chap.get('villages', [])
    changes = [(x - 1, y - 1, 3, 2,
                _drawn_block(tileset, CH05_RUIN_ORIGIN, (3, 2), 'TERRAIN_RUINS_REGULAR',
                             '%s desecrated' % v['id']),
                '%s desecrated -- raided before the party reached it' % v['id'])
               for v in villages for x, y in [v['tile']]]
    changes += [(v['tile'][0], v['tile'][1], 1, 1,
                 [_snowy_metatile_for(tileset, 'TERRAIN_VILLAGE_CLOSED')],
                 '%s visited' % v['id'])
                for v in villages]
    return changes


def ch05_location_events(chap):
    """ch05's Location list: the four reliquaries, each armed with its race flag, plus the
    elven store. Vanilla Ch5's own list, one for one (four villages, an armory and a vendor)."""
    return location_events(chap.get('villages', []),
                           {vid: slot[0] for vid, slot in CH05_VILLAGE_SLOTS.items()},
                           CH05_SHOPS, flags=CH05_VILLAGE_FLAGS)


def assert_village_tiles_visitable(chap, maps_dir, stem):
    """Guard (#205): a village the YAML declares must stand on terrain FE8 will let a unit visit.

    `CanUnitVisit`/the Visit menu item (bmmenu.c:735) checks the TERRAIN under the unit before it
    ever looks at the location event -- HOUSE, INN, RUINS_VILLAGE or VILLAGE_REGULAR -- so a
    `Village()` entry on scenery is a reward that silently does not exist. That is precisely what
    shipped: the snowy reskin mapped vanilla's village metatile onto ruins, the map still drew a
    cottage, and ch04's only material reward was unobtainable for the whole slice.
    """
    width, height, terrain = _map_terrain_grid(maps_dir, stem)
    ids = terrain_ids()
    visitable = {ids[name] for name in
                 ('TERRAIN_HOUSE', 'TERRAIN_INN', 'TERRAIN_RUINS_VILLAGE',
                  'TERRAIN_VILLAGE_REGULAR')}
    for village in chap.get('villages', []):
        x, y = village['tile']
        if not (0 <= x < width and 0 <= y < height):
            sys.exit('ERROR: village %r is at (%d, %d), off the %dx%d %s map'
                     % (village['id'], x, y, width, height, stem))
        if terrain[y][x] not in visitable:
            sys.exit('ERROR: village %r at (%d, %d) stands on terrain 0x%02x -- FE8 offers Visit '
                     'only on house/inn/village terrain (bmmenu.c), so its reward is '
                     'unobtainable. Paint a village tile there (#205).'
                     % (village['id'], x, y, terrain[y][x]))


def vanilla_village_gifts(layout, eventinfo=None, eventscript=None):
    """{(x, y): ITEM_ enum} -- what vanilla hands out at each village on `layout`'s chapter.

    Read from HEAD, like every other vanilla fact. The tile comes from the Location list's
    `Village(flag, script, x, y)` entries; the ITEM is a RAW id inside that script's
    `SVAL(EVT_SLOT_3, <id>)`, which is why it is easy to have and never look at.
    """
    stem = re.sub(r'Map$', '', layout).lower()          # Ch5Map -> ch5
    if eventinfo is None:
        eventinfo = _vanilla_decomp_text_at_head('src/events/%s-eventinfo.h' % stem)
    if eventscript is None:
        eventscript = _vanilla_decomp_text_at_head('src/events/%s-eventscript.h' % stem)
    by_id = {int(v, 16): n for n, v in re.findall(
        r'(ITEM_\w+)\s*=\s*(0x[0-9A-Fa-f]+)',
        _vanilla_decomp_text_at_head('include/constants/items.h'))}
    gifts = {}
    for script, x, y in re.findall(
            r'Village\(\s*[^,]+,\s*(\w+),\s*(\d+),\s*(\d+)\s*\)', eventinfo):
        body = eventscript.split('EventListScr %s[] = {' % script, 1)
        if len(body) < 2:
            continue                                    # script lives elsewhere; nothing to read
        match = re.search(r'SVAL\(EVT_SLOT_3,\s*(0x[0-9A-Fa-f]+|\d+)\)', body[1].split('};', 1)[0])
        if match:
            gifts[(int(x), int(y))] = by_id.get(int(match.group(1), 0))
    return gifts


def assert_village_gifts_match_vanilla(chap, item_ids, gifts=None):
    """Guard (#25): on a RETILE, which gift sits on which tile is vanilla's decision.

    A retile inherits vanilla's terrain (`validate_terrain_matches_vanilla`); this is the same
    rule one layer up, for the rewards standing on that terrain. It is worth a gate because the
    failure is invisible to every other one: swap two gifts and the item set is identical, the
    economy total is identical, and `difficulty.py` counts the SET, not the tiles -- so the
    parity read still says PARITY while the chapter's risk/reward is inverted.

    That is exactly what ch05 shipped. `(12,19)` is the south-east site and the turn-2 eruption
    pair spawns at `(14,16)/(14,15)`, right beside it: vanilla puts its RICHEST gift there
    (Dracoshield, 8000g) and its cheapest at `(5,1)` (Torch, 500g), which sits behind the whole
    enemy line. Ours had them swapped, paying the most for the safest errand in a chapter whose
    structure IS the race for the reward-sites.

    Deliberate divergence stays cheap -- a village may carry `vanilla_gift_divergence: <why>` and
    is then skipped by name. The default is inheritance because exceptions are rarer than
    re-deriving four placements every time (Nicolas, 2026-08-07).

    Only runs for a chapter whose `map:` block names a `vanilla_layout:`; a from-scratch canvas
    has no vanilla to inherit from.
    """
    layout = (chap.get('map') or {}).get('vanilla_layout')
    if not layout:
        return
    if gifts is None:
        gifts = vanilla_village_gifts(layout)
    for village in chap.get('villages', []):
        why = village.get('vanilla_gift_divergence')
        if why:
            continue
        tile = tuple(village['tile'])
        want = gifts.get(tile)
        if want is None:
            continue        # vanilla has no village on that tile -- a site we ADDED, not moved
        reward = (village.get('visit_reward') or [{}])[0].get('id')
        got = item_ids.get(reward)
        if got is None:
            sys.exit('ERROR: village %r gives %r, which is not in this chapter\'s item map -- '
                     'add it to CHNN_ITEM_IDS so the gift can be checked and injected'
                     % (village['id'], reward))
        if got != want:
            sys.exit(
                'ERROR: village %r at (%d, %d) gives %s, but vanilla %s hands out %s there. On a '
                'retile the gift PLACEMENT is vanilla\'s -- swapping two gifts keeps the item set '
                'and the economy total identical (so the parity read still says PARITY) while '
                'inverting which site is worth defending. If the move is deliberate, say so with '
                '`vanilla_gift_divergence: <why>` on that village.'
                % (village['id'], tile[0], tile[1], got, layout, want))


def _is_blank_metatile(tileset, metatile):
    """True if a metatile is a single flat colour -- i.e. DECLARED in the terrain table but never
    painted. snowy-bern has one of these on TERRAIN_BRIDGE_SNAG, and writing it into a map change
    put a black square in the river while every terrain byte read correctly (#214)."""
    return len(set(tileset.metatile_image(metatile).convert('RGB').getdata())) <= 1


def _snowy_metatile_for(tileset, terrain_name, prefer=None):
    """The lowest PAINTED metatile carrying `terrain_name` (or `prefer` if it qualifies).

    Map-change tiles are chosen by the TERRAIN they must produce, not copied as numbers: the
    reskin renumbers everything, so a hardcoded metatile is a stale tile waiting to happen (#205
    is the whole cautionary tale). Blank metatiles are skipped -- a tileset can carry a terrain id
    on an unpainted tile, and the terrain byte alone reads as correct while the map shows a hole.
    Fails loudly if the tileset cannot express the terrain with real art."""
    want = terrain_ids()[terrain_name]
    if (prefer is not None and tileset.terrain(prefer) == want
            and not _is_blank_metatile(tileset, prefer)):
        return prefer
    for m in range(1024):
        if tileset.terrain(m) == want and not _is_blank_metatile(tileset, m):
            return m
    sys.exit('ERROR: the tileset has no PAINTED metatile carrying %s -- a map change needs one '
             '(a declared-but-unpainted tile renders as a solid block)' % terrain_name)


def ch04_map_changes(chap, maps_dir):
    """ch04's tile flips (#214): the snag falling into a crossing, and each visited village
    closing its door.

    Returns the `map_changes_asm` change list. Both are vanilla Ch4's own changes, kept at
    vanilla's positions (our retile preserved them) but resolved to OUR tileset's metatiles by
    terrain. Without the village entry a visited village stays looking un-visited, which vanilla
    never does."""
    import map_tileset_tool as mt
    tileset = mt._tileset_from_dir(os.path.join(maps_dir, 'tilesets', WINTER_TILESET))
    x, y = CH04_SNAG_POS
    w, h = CH04_SNAG_SIZE
    changes = [(x, y, w, h,
                [_snowy_metatile_for(tileset, terrain, prefer=metatile)
                 for terrain, metatile in zip(CH04_SNAG_TERRAIN, CH04_SNAG_TILES)],
                'the snag falls -> a crossing at (%d, %d)' % (x, y + 1))]
    changes += [(v['tile'][0], v['tile'][1], 1, 1,
                 [_snowy_metatile_for(tileset, 'TERRAIN_VILLAGE_CLOSED')],
                 '%s visited' % v['id'])
                for v in chap.get('villages', [])]
    return changes


def ch04_moose_script(unit_symbol, pid, msg, camera_at, flee_route):
    """The moose-flees beat: the quarry is sighted in a clearing, then simply gone.

    Locked staging (chapter YAML, 2026-07-03): "A shape in the fog ahead: the white moose,
    huge and still in the clearing, watching them. A heartbeat -- then it turns and is simply
    gone, silent, southeast." So: pan to it, hold (the heartbeat), RBG's one line, then move it
    as a normal unit over the bridge and off the tomb-side edge before DISA. It never speaks --
    locked as a mute white ghost, and ch05 re-locks that -- so the only voice here is RBG's.

    The moose is LOADed by this script rather than at chapter start: under fog it would
    otherwise sit invisible on the map for several turns and could be attacked, and it is
    uncatchable by design (canon). Sighting it and losing it is the whole beat.

    PLAYER-ONLY, and that guard is not optional. The AREA that fires this lives in the Misc
    list, and FE8 polls that list at the end of EVERY unit's action -- playerphase.c and
    cp_perform.c both PROC_CALL_2(RunPotentialWaitEvents) -- while EvCheck0B_AREA (eventinfo.c)
    tests gActiveUnit's position with NO faction check. The clearing is where the turn-1 monster
    line stands, so unguarded, a Revenant ending its move there plays RBG's "After it!" to an
    empty clearing on turn 1. Caught in-engine, not by reading: `recordch04reveal` filmed it
    firing during turn 1's ENEMY phase with no blue unit anywhere in the rect.

    An early ENDA would not be enough either: StartEventFromInfo SetFlag()s the AREA's one-shot
    BEFORE it CallEvent()s the script, so bailing out would spend the beat forever. Vanilla
    already ships the whole answer as EventScr_UnTriggerIfNotFaction (eventcall.h; ch13b/ch15b
    use it exactly this way) -- it clears the TRIGGERED event id, re-arming the AREA, and ENDBs
    the entire event rather than just its own frame.
    """
    cx, cy = camera_at
    if not flee_route:
        sys.exit('ERROR: the white moose needs at least one authored flee-route waypoint')
    move = ['    SVAL(EVT_SLOT_D, 0x0) /* authored REDA route; one pair per waypoint */']
    for x, y in flee_route:
        move += [
            '    SVAL(EVT_SLOT_1, 0x%X) /* (%d, %d), normal unit movement */'
            % ((y << 6) | x, x, y),
            '    SENQUEUE1',
            '    SVAL(EVT_SLOT_1, 0x0)',
            '    SENQUEUE1',
        ]
    move += [
        '    MOVE_DEFINED(%s) /* continuous route over the bridge, then southeast */' % pid,
        '    ENUN',
    ]
    return ('{\n'
            '    SVAL(EVT_SLOT_2, FACTION_ID_BLUE) /* only the PARTY sights the quarry */\n'
            '    CALL(EventScr_UnTriggerIfNotFaction) /* a monster wandered in: re-arm, abort */\n'
            '    LOAD1(0x1, %s) /* the white moose, neutral -- sighted, never fought */\n'
            '    ENUN\n'
            '    CAMERA2(%d, %d) /* 15-tile map center: pin x=0, never show wrapped map memory */\n'
            '    MUSS(SONG_TENSION)\n'
            '    CUMO_CHAR(%s) /* the shape in the fog: huge, still, watching */\n'
            '    STAL(75) /* the heartbeat -- hold on it before it breaks */\n'
            '    CURE\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X) /* RBG: "After it!" */\n'
            '    TEXTEND\n'
            '    REMA\n'
            '%s\n'
            '    DISA(%s) /* ...and is simply gone */\n'
            '    MURE(0x2) /* restore the map BGM (MURE takes a fade speed -- cf. ch12a/ch15a) */\n'
            '    EVBIT_T(7)\n'
            '    ENDA\n}'
            % (unit_symbol, cx, cy, pid, msg, '\n'.join(move), pid))


def ch04_enemy_rows(chap, arrives_turn=None):
    """Build one Ch04 UnitDefinition row per authored position for a deployment wave.

    `arrives_turn=None` selects the turn-1 line; numbered values select that reinforcement
    wave. A group-level `item_drop` denotes one dropper, not one copy per position.
    """
    rows = []
    for enemy in chap['enemy_units']:
        if enemy.get('arrives_turn') != arrives_turn:
            continue
        cls = CH04_CLASS_IDS[enemy['class']]
        pid = CH04_MONSTER_PIDS[enemy['class']]
        inventory = []
        for item in enemy.get('inventory', []):
            key = item.get('fe_base') or item['id']
            inventory.append(CH04_ITEM_IDS[key])
        drop = enemy.get('item_drop')
        ai = CH04_AI[enemy.get('ai_pattern', 'defensive')]
        for index, (x, y) in enumerate(enemy['positions']):
            items = list(inventory)
            is_dropper = bool(drop) and index == 0
            if is_dropper:
                items.append(CH04_ITEM_IDS[drop])
            rows.append(_enemy_unit_entry(
                pid, cls, int(enemy['level']), bool(enemy.get('autolevel')),
                x, y, ', '.join(items) or '0', ai,
                ' /* %s -- %s */' % (enemy['id'], enemy['name']),
                itemdrop=is_dropper))
    return rows


def _ch04_reveal_wave(chap):
    """The turn-2 convertible pack -- the Mauthe Doog wave Marty parleys (its YAML `parley`
    block). By convention its FIRST authored tile is the pack LEADER (-> Lupin, placed red);
    the remaining tiles are the generic wolves (CUSN'd green in place on the parley)."""
    wave = next((e for e in chap['enemy_units']
                 if e.get('arrives_turn') == 2 and e.get('parley')), None)
    if wave is None:
        sys.exit('ERROR: ch04 has no turn-2 convertible (parley) wave')
    return wave


def _ch04_wave_pack_kit(wave):
    """(class_enum, ai, items) for a ch04 enemy wave, read from its authored YAML (no drift).

    The pack keeps this kit through the parley: CUSN changes a unit's FACTION, nothing else,
    so the converted wolves fight on with the same class, items and (aggressive) AI -- which
    is the point, since "the wolves turn the tide" is what the parley buys."""
    cls = CH04_CLASS_IDS[wave['class']]
    ai = CH04_AI[wave.get('ai_pattern', 'defensive')]
    items = [CH04_ITEM_IDS[i.get('fe_base') or i['id']] for i in wave.get('inventory', [])]
    return cls, ai, ', '.join(items) or '0'


def ch04_turn2_reveal_rows(chap, lupin):
    """The turn-2 wolf-pack reveal wave: the convertible Mauthe Doog pack with its LEADER tile
    reassigned to Lupin (red, his CHARACTER_ slot pid, Cavalier under the hood). 5 generic
    Mauthe Doogs + Lupin = 6 -- holds the turn-2 parity count (ch04_enemy_rows still reports 6
    for the difficulty read; the split is injector-side only). Marty's parley CUSNs the surviving
    generics green in place, then CUSAs Lupin blue. `lupin` = an on_map_talk_recruits row.
    Lupin is placed at his YAML level, NOT autolevelled -- his stats persist through the CUSA, so
    he joins as the intended fresh Cavalier (a deliberately weak hostile that telegraphs "talk, don't kill").

    Each generic takes its OWN pid (CH04_PACK_PIDS, in tile order) -- the parley addresses them
    one at a time, and a shared pid can only ever be found once (#203)."""
    wave = _ch04_reveal_wave(chap)
    cls, ai, items = _ch04_wave_pack_kit(wave)
    leader_pos, generic_pos = wave['positions'][0], wave['positions'][1:]
    if len(generic_pos) != len(CH04_PACK_PIDS):
        sys.exit('ERROR: ch04 pack is %d generics but CH04_PACK_PIDS has %d pids -- the '
                 'parley converts BY PID, so every wolf needs one'
                 % (len(generic_pos), len(CH04_PACK_PIDS)))
    _uid, slot, class_enum, deploy_class, level = lupin
    lupin_row = _enemy_unit_entry(
        char_symbol(slot), deploy_class, level, False,
        leader_pos[0], leader_pos[1], ', '.join(CLASS_LOADOUT[class_enum]),
        CH04_AI['aggressive'], ' /* lupin -- hostile pack leader (red; Marty parleys him blue) */')
    generics = [_enemy_unit_entry(
        pid, cls, int(wave['level']), bool(wave.get('autolevel')), x, y, items, ai,
        ' /* %s %d/%d -- %s (generic pack; own pid so the parley can convert it) */'
        % (wave['id'], i + 1, len(generic_pos), wave['name']))
        for i, (pid, (x, y)) in enumerate(zip(CH04_PACK_PIDS, generic_pos))]
    return [lupin_row] + generics


def assert_pack_pids_addressable(chap, pack_pids):
    """Guard (#198 review, re-aimed by #203): every wolf the parley converts must be reachable
    by its own pid, and by nobody else's.

    CUSN and CHECK_ALIVE resolve through GetUnitFromCharId, which returns the FIRST unit
    matching a pid. So two failures are silent, and both leave the difficulty read looking
    correct: a pid repeated WITHIN the pack is unaddressable (the second CUSN re-finds the wolf
    the first turned green -- the original #203 defect), and a pid shared with anything else
    ch04 places converts that unit instead.
    """
    dupes = sorted({p for p in pack_pids if list(pack_pids).count(p) > 1})
    if dupes:
        sys.exit('ERROR: ch04 pack pids repeat (%s) -- CUSN finds the FIRST match, so the '
                 'second wolf on a shared pid can never be converted. Give each its own.'
                 % ', '.join(dupes))
    # Every OTHER pid ch04 puts on the map. The reveal wave is skipped: its class pid feeds the
    # difficulty read only (ch04_enemy_rows), because the pack itself is placed by
    # ch04_turn2_reveal_rows on these very pack_pids.
    wave = _ch04_reveal_wave(chap)
    elsewhere = {CH04_MOOSE_PID: 'the white moose'}
    for enemy in chap.get('enemy_units', []):
        pid = CH04_MONSTER_PIDS.get(enemy.get('class'))
        if pid and enemy is not wave:
            elsewhere.setdefault(pid, 'the %r wave' % enemy['id'])
    clashes = ['%s (%s)' % (p, elsewhere[p]) for p in pack_pids if p in elsewhere]
    if clashes:
        sys.exit('ERROR: ch04 pack pid collision -- %s. Marty\'s parley would convert that '
                 'unit instead of the wolf. Draw the pack from the free 0xB0..0xB9 band.'
                 % ', '.join(clashes))


def parley_recruiters(unit):
    """The recruiter set for a GATED talk recruit = ONLY the speaker the unit's own `parley.by`
    names, as a one-entry CHARACTER_ list for talk_recruit_wiring.

    The counterpart to talk_recruiters ("any core party member", ch03's Trex). A chapter picks
    between them; the wiring downstream is identical either way. Gated recruits are the ones
    whose fiction is carried by ONE character, so the recruiter is authored data rather than a
    roster query: ch04's Marty->Lupin (Nicolas 2026-07-21 -- the reveal centres Marty's creature
    diplomacy) and ch05's Basil->Sahnar (Sahnar does not weigh the argument, she RECOGNISES
    Basil -- lore/sahnar.md; anyone else gets the killing edge).

    `unit` is whatever dict carries the parley block -- ch04 hands it the convertible WAVE,
    ch05 the convertible ENEMY entry. Both are just "the thing being parleyed with", which is
    why this needs neither the campaign nor the chapter."""
    by = (unit.get('parley') or {})['by']
    if by not in PORTRAIT_MAP:
        sys.exit('ERROR: parley.by %r is not a cast member with a PORTRAIT_MAP slot -- a Talk '
                 'can only be initiated by a unit the engine can address' % by)
    return [char_symbol(PORTRAIT_MAP[by])]


def ch04_reveal_cutscene_script(reveal_symbol, lupin_char, beat_msgs, camera_xy):
    """The turn-2 wolf-pack REVEAL cutscene (Stage 2c), riding the existing turn-2 LOAD1 (the
    vanilla Ch4 EventScr_089F199C shape: CAMERA2 -> STAL -> LOAD1/ENUN -> MUSC -> CUMO_CHAR ->
    STAL -> TEXT beats -> EVBIT_T). ON-MAP (no BACG -- the chapter continues on the battle map):
    pan to the NW fog, burst the pack in, focus Lupin (the commander -- intelligence shown by
    ACTION), then the beats PLANT the parley (Lupin commands; Marty reads it and flags "talk to
    it" -- the cutscene IS the parley teaching). `beat_msgs` = (lupin_command, marty_flag). Stub
    lines now; Stage 4 finalizes the dialogue via the dialogue-pass skill."""
    cx, cy = camera_xy
    beats = ''.join('    TEXTSTART\n    TEXTSHOW(0x%X)\n    TEXTEND\n    REMA\n' % m
                    for m in beat_msgs)
    return ('{\n'
            '    CAMERA2(%d, %d) /* pan to the NW fog where the pack bursts */\n'
            '    STAL(15)\n'
            '    LOAD1(0x1, %s) /* turn-2 reveal: 5 Mauthe Doogs + red Lupin */\n'
            '    ENUN\n'
            '    MUSC(SONG_TENSION)\n'
            '    CUMO_CHAR(%s) /* focus the pack leader -- Lupin commands (intelligence by ACTION) */\n'
            '    STAL(45)\n'
            '    CURE\n'
            % (cx, cy, reveal_symbol, lupin_char)
            + beats +
            '    EVBIT_T(7)\n'
            '    ENDA\n}')


def _read_map_metatile(maps_dir, stem, x, y):
    """Return the metatile index painted at (x, y) on a compiled .mar layout. compile_layout
    stores each cell as metatile<<5 with no header (map_tileset_tool), row-major over the
    width from the paired .json -- so reading the door's OPEN tile off the map itself tracks
    any re-retile (no hand-copied tile numbers to drift)."""
    with open(os.path.join(maps_dir, stem + '.json'), encoding='utf-8') as f:
        w = json.load(f)['width']
    with open(os.path.join(maps_dir, stem + '.mar'), 'rb') as f:
        mar = f.read()
    return struct.unpack_from('<H', mar, (y * w + x) * 2)[0] >> 5


TERRAIN_TABLE_OFFSET = 8192     # a tile config is 8192 B TSA + 1024 B terrain (map_tileset_tool)


def terrain_ids():
    """{TERRAIN_NAME: id} from the decomp's own enum at HEAD -- so a terrain is named, never a
    bare number, and the names track the decomp rather than a copy of it."""
    return {name: int(value, 0) for name, value in re.findall(
        r'(TERRAIN_[A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)',
        vanilla_decomp_text('include/constants/terrains.h'))}


def _map_terrain_grid(maps_dir, stem):
    """(width, height, terrain[y][x]) for a painted chapter layout, resolved through its OWN
    tileset's terrain table. Reads the campaign tileset asset, not the decomp's copy of it --
    ours is the committed source, the decomp's is the untracked artifact injection writes."""
    with open(os.path.join(maps_dir, stem + '.json'), encoding='utf-8') as f:
        meta = json.load(f)
    width, tileset = meta['width'], meta.get('tileset', WINTER_TILESET)
    with open(os.path.join(maps_dir, 'tilesets', tileset, tileset + '.bin'), 'rb') as f:
        terrain = f.read()[TERRAIN_TABLE_OFFSET:]
    with open(os.path.join(maps_dir, stem + '.mar'), 'rb') as f:
        mar = f.read()
    height = len(mar) // 2 // width
    return width, height, [
        [terrain[struct.unpack_from('<H', mar, (y * width + x) * 2)[0] >> 5]
         for x in range(width)] for y in range(height)]


def _class_terrain_move_costs(table):
    """One class's terrain movement-cost row, indexed by terrain id (entry <= 0 = the class may
    not enter that terrain), read from the decomp at HEAD -- data_terrains.c is a PATCHED file,
    so the working tree is not the vanilla answer.

    The rows are DESIGNATED initializers keyed by name (`[TERRAIN_FOREST] = 2`), not a positional
    list, so they must be resolved through the terrain enum. Reading them positionally silently
    produces a table that is wrong in a way that still looks plausible -- every terrain walkable,
    because the names themselves carry digits (TERRAIN_C_ROOM_09, TERRAIN_TILE_2E) that a naive
    number scan picks up as costs."""
    text = vanilla_decomp_text('src/data_terrains.c')
    match = re.search(r'\b%s\[\]\s*=\s*\{(.*?)\};' % re.escape(table), text, re.S)
    if not match:
        sys.exit('ERROR: no movement-cost table %s in the decomp' % table)
    ids = {name: int(value, 0) for name, value in re.findall(
        r'(TERRAIN_[A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)',
        vanilla_decomp_text('include/constants/terrains.h'))}
    costs = [-1] * (max(ids.values()) + 1)   # a terrain the row omits stays impassable
    for name, value in re.findall(r'\[(TERRAIN_[A-Z0-9_]+)\]\s*=\s*(-?\d+)', match.group(1)):
        costs[ids[name]] = int(value)
    return costs


def reachable_tiles(terrain, costs, start):
    """The set of tiles a unit with `costs` can WALK to from `start` (4-neighbour flood fill,
    the engine's own rule: costs[terrain] < 0 means it may not enter)."""
    height, width = len(terrain), len(terrain[0])
    seen, queue = {start}, [start]
    while queue:
        x, y = queue.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen
                    and costs[terrain[ny][nx]] > 0):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def assert_scripted_move_reachable(maps_dir, stem, start, dest, mov_table, who):
    """A scripted MOVE(...)+ENUN to a tile its unit cannot WALK to NEVER RETURNS: the event
    engine waits on a path that does not exist and the chapter hangs, with the unit standing
    exactly where it was. Nothing upstream catches it -- the destination can be perfectly good
    terrain, `make` stays green, and the beat only wedges the game when it actually fires.

    Found the hard way (ch04 #24 Stage 4): the white moose flees to the map's NE corner, which
    is TERRAIN_PLAINS and looks fine, but is sealed off from its own clearing by a wall of
    TERRAIN_CLIFF. The sighting soft-locked the chapter the first time a party unit triggered
    it -- and `smoke_ch04` stayed green throughout, because an idling party never walks into the
    clearing to trigger it.

    So: flood-fill the map with the unit's class movement-cost row and reject any destination
    outside the region reachable from where the script loads it.
    """
    _, _, terrain = _map_terrain_grid(maps_dir, stem)
    costs = _class_terrain_move_costs(mov_table)
    reachable = reachable_tiles(terrain, costs, start)
    if dest not in reachable:
        north_east = sorted(reachable, key=lambda t: (t[1] - t[0]))[0]
        sys.exit(
            'ERROR: %s cannot walk from %s to %s on %s -- the MOVE would hang the chapter.\n'
            '       destination terrain is 0x%02X (cost %d); it is simply cut off from the '
            'start.\n'
            '       most north-east tile it CAN reach: %s'
            % (who, start, dest, stem, terrain[dest[1]][dest[0]],
               costs[terrain[dest[1]][dest[0]]], north_east))


def assert_green_recruit_placement(chap, maps_dir, stem, pos, mov_table, who, must_reach=None):
    """Where a GREEN on-map recruit is LOADed has three ways to be quietly wrong, and none of
    them fails the build or a load-test. Gate all three at injection time.

    1. **On a deploy tile.** The prep flow fills every one of the chapter's `deploy_slots`
       (the cap IS the slot count -- decisions.md "How the deploy cap + prep screen are actually
       wired"), so a green body parked on one silently costs the player a deployment on a map
       balanced for the full cap. Cheapest possible bug to make: the recruit's own vanilla twin
       usually STANDS on one, because in vanilla it is a blue party member (ch05: Natasha is
       BLUE in UnitDef_Event_Ch5Ally, on what is now one of our nine tiles).
    2. **Impassable.** A recruit on terrain its own class cannot occupy is unreachable and
       untalkable -- the chapter just quietly loses its recruit.
    3. **Walled off from the unit it must reach.** An escort-recruit exists to cross the map;
       if the flood-fill says it cannot, the set-piece is dead on arrival and the only symptom
       is a player who never manages the Talk.

    `must_reach` is the tile the recruit has to be able to WALK to (ch05: Sahnar's). Reuses
    reachable_tiles, the same flood fill assert_scripted_move_reachable runs."""
    slots = [tuple(s) for s in chap['deployment']['deploy_slots']]
    if tuple(pos) in slots:
        sys.exit('ERROR: %s is placed on %s, which is one of the %d PREP deploy tiles -- the '
                 'green body would cost the player a deployment.' % (who, tuple(pos), len(slots)))
    _, _, terrain = _map_terrain_grid(maps_dir, stem)
    costs = _class_terrain_move_costs(mov_table)
    if costs[terrain[pos[1]][pos[0]]] <= 0:
        sys.exit('ERROR: %s is placed on %s, terrain 0x%02X, which its class cannot enter.'
                 % (who, tuple(pos), terrain[pos[1]][pos[0]]))
    if must_reach is not None:
        reachable = reachable_tiles(terrain, costs, tuple(pos))
        if tuple(must_reach) not in reachable:
            sys.exit('ERROR: %s at %s cannot WALK to %s -- the escort recruit is unreachable, '
                     'so the Talk can never happen.' % (who, tuple(pos), tuple(must_reach)))


def map_changes_asm(symbol, changes):
    """The per-chapter MapChange array, for any chapter that flips tiles (#23 ch03 chests/doors,
    #214 ch04's snag + visited village).

    FE8 flips tiles through a per-chapter MapChange array: a chest runs
    CallChestOpeningEvent(GetMapChangeIdAt(x, y), item), a door CallTileChangeEvent(...)
    (eventinfo.c), and a destroyed obstacle -- a SNAG -- ApplyMapChangesById(GetMapChangeIdAt(...))
    from UpdateObstacleFromBattle (bmbattle.c). All three find the change whose region covers the
    tile and write its tiles into gBmMapBaseTiles. Lookup is by POSITION, so one array serves every
    kind and ids only need to stay unique.

    `changes` = [(x, y, w, h, [metatile, ...], why), ...] in ROW-MAJOR order per region.

    struct MapChange { s8 id; u8 xOrigin, yOrigin, xSize, ySize; u8 pad[3]; const void* data; }
    (12 B; data at 0x08). Tile data is metatile<<2 (the gBmMapBaseTiles encoding). The array
    terminates on id < 0. The caller registers `symbol` as a fresh gChapterDataAssetTable word and
    points the host slot's map.changeLayerId at it (_inject_tile_changes)."""
    lines = ['', '/* Manchego Stars %s */' % symbol,
             '\t.align 2, 0', '\t.global %s' % symbol, '%s:' % symbol]
    blobs = []
    for mid, (x, y, w, h, tiles, why) in enumerate(changes):
        if len(tiles) != w * h:
            sys.exit('ERROR: map change %d at (%d, %d) is %dx%d but carries %d tiles'
                     % (mid, x, y, w, h, len(tiles)))
        sym = '%s_tiles_%d' % (symbol, mid)
        lines.append('\t.byte %d, %d, %d, %d, %d, 0, 0, 0 /* %s */\n\t.word %s'
                     % (mid, x, y, w, h, why, sym))
        blobs.append('%s:\n%s' % (sym, '\n'.join(
            '\t.hword %d /* metatile %d */' % (m << 2, m) for m in tiles)))
    lines.append('\t.byte -1, 0, 0, 0, 0, 0, 0, 0 /* terminator (id < 0) */\n\t.word 0')
    return '\n'.join(lines + blobs)


def _inject_tile_changes(symbol, changes, host_index):
    """Emit `changes` as `symbol`, register it in gChapterDataAssetTable and point host slot
    `host_index` at it (GetChapterMapChangesPointer -> gChapterDataAssetTable[changeLayerId],
    chapterdata.c). Must run AFTER _retarget_host_chapter, which zeroes changeLayerId."""
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write(map_changes_asm(symbol, changes) + '\n')
    idx = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [symbol])
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    settings['chapters'][host_index]['map']['changeLayerId'] = idx
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    return idx


def _inject_ch03_tile_changes(chap, maps_dir, host_index):
    """Author the ch03 chest + door tile-changes + point slot `host_index` at them (#23).

    Emits MS_Ch03MapChanges (chests then doors -- see _ch03_tile_changes_asm), registers it as
    a fresh gChapterDataAssetTable word, and sets the host slot's map.changeLayerId to that index
    (GetChapterMapChangesPointer -> gChapterDataAssetTable[changeLayerId], chapterdata.c). Each
    door's open tile is read off the painted map (the metatile directly below the door cell)."""
    changes = [(c['position'][0], c['position'][1], 1, 1, [CH03_CHEST_OPEN_TILE],
                'chest %d -> %d on loot' % (CH03_CHEST_CLOSED_TILE, CH03_CHEST_OPEN_TILE))
               for c in chap.get('chests', [])]
    # An opened door becomes the passable tile directly BELOW it (Nicolas 2026-07-11), read off
    # the painted map so a re-retile cannot leave a hand-copied tile number behind.
    changes += [(d['position'][0], d['position'][1], 1, 1,
                 [_read_map_metatile(maps_dir, CH03_LAYOUT[1],
                                     d['position'][0], d['position'][1] + 1)],
                 'door opens to the floor below')
                for d in chap.get('doors', [])]
    return _inject_tile_changes('MS_Ch03MapChanges', changes, host_index)


def inject_ch03(campaign, boot=False, verbose=True):
    """Host for Ch3 "The Termalaine Mine" (#23) on chapter slot 4: register the cave-interior
    tileset + the painted layout, wire the real PREP deploy of the classed party + the 10
    vanilla-Ch3-parity enemies (reflavored kobolds / grell / svirfneblin) at their vanilla
    tiles, strip cutscenes, and leave a walkable, playable map.

    Deploy = the vanilla prep-chapter idiom (cf. inject_ch01/inject_ch02): a never-LOADed
    deploy-cap template (UnitDef_Event_Ch4Ally, sized to cast_available_at(3) over the YAML
    deploy_slots) + a Preparations CALL that fields the roster (the lord force-deployed).
    The real ch02->ch03 chain calls this with boot=False: ch02's ending MNC2(0x4) lands here
    and the party that PERSISTS from ch02 feeds PREP (main() hosts ch03 in every non-boot build).
    `boot` (the --ch03-boot debug path, New Game straight to slot 4) instead LOADs an ARMED party
    seed so PREP has a party to pick from from a COLD New Game -- a standalone-playtest crutch only.

    The DefeatBoss(grell) WIN is wired: Misc DefeatBoss AFEV + the grell's flagged (EVFLAG_DEFEAT_BOSS)
    defeat quote + a minimal ending script (victory -> dev-placeholder landing until ch04 hosts).
    Trex's TALK RECRUIT (#23 item 2) stands GREEN in its own table; ANY core party member Talks
    to him -> the shared recruit script CUSA-flips him BLUE (the Colm/Neimi pattern -- one CHAR entry
    per field candidate). The OPENING (chapter_start, over the Targos-winter BG), Trex's light
    turn-1 ENTRANCE (Colm pattern, on-map), and the ENDING (chapter_end, over the BG -> the
    dev-placeholder landing) cutscenes are wired here, as is the mid-map RBG-EXECUTION beat: the
    Icewind Brute rides a unique miniboss pid + a silent flagged defeat quote, and a Misc AFEV fires
    the on-map execution cutscene once on its death (the mirror of the boss WIN). DEFERRED (follow-up
    passes): chests/doors; title-card art; enemy/boss art; ch03's own ending still parks on the
    dev-placeholder until ch04 hosts (then it MNC2s onward like this chapter's ch02->ch03 chain)."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH03_CHAPTER_YAML)

    # 0. Cutscene beat splits, from the locked chapter YAML (cf. inject_ch01/ch02). The
    #    opening + ending play over the reused Targos-winter BG; trex_entrance is a LIGHT
    #    on-map turn-1 beat (Colm's pattern). The midmap RBG-execution beat is a follow-up.
    op_card, op_beats = _split_event_beats(chap, 'chapter_start', 'ch03 opening', CH03_OPENING_MSGS)
    end_card, end_beats = _split_event_beats(chap, 'chapter_end', 'ch03 ending', CH03_ENDING_MSGS)
    trex_entr = next(e for e in chap['events'] if e.get('trigger') == 'trex_entrance')['script']
    # Midmap RBG-execution beat: on-map (no BG, no card), 3 beats (A/B/C) over 0x9AF..0x9B1.
    _mid_card, mid_beats = _split_event_beats(chap, 'midmap', 'ch03 midmap', CH03_MIDMAP_MSGS,
                                              card_required=False)
    # Speaker -> face: cast via PORTRAIT_MAP; narration faceless (opaque #58 box); the boy-crier
    # rides a generic villager mug (his line names Speaker Masthew -- book p.93, Oarus Masthew).
    # The kobold-brute now has a custom mug on the Caellach guest slot -> it resolves through the
    # GUEST_PORTRAIT_MAP fallback (checked after cast), so its midmap snarl is a FACED bubble.
    cut_special = {'narration': None, 'boy-crier': CH03_CRIER_FID}
    cut_fid = _make_fid(cut_special, 'ch03 unknown cutscene speaker', fallback=GUEST_PORTRAIT_MAP)
    # RBG anchors mid-right through the opening (the leader who answers): the beat-A crier
    # two-shot + the beat-C Pinky/RBG flyover two-hander stage cleanly without face-flashing.
    # The midmap Brute also anchors mid-right (facing Pinky at mid-left) -- its A-beat preload +
    # its A3 snarl land on the same podium; it never shares a beat with RBG, so no collision.
    op_home = {'prof-rbg': '[OpenMidRight]', 'kobold-brute': '[OpenMidRight]'}

    # 1. Map: register the cave-interior tileset (first chapter to use it) + the painted
    #    layout, point slot 4 at them, and borrow slot 6's defeat_boss goal banner.
    _register_tileset(campaign, CH03_TILESET, 'Cave',
                      'Manchego Stars cave-interior tileset (#23/#40)')
    indices = _register_chapter_map(maps_dir, CH03_LAYOUT, 'Manchego Stars ch03 layout (#23)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH03_HOST_INDEX, CH03_GOAL_DONOR, 'defeat_boss',
        'ERROR: slot %d goal is not the vanilla defeat_boss template (ch03 DefeatBoss donor)'
        % CH03_GOAL_DONOR, indices, chap['chapter_number'], CH03_EVENT_GROUP,
        (CH03_GOAL_WINDOW_MSG, CH03_GOAL_STATUS_MSG))

    # 2. Rosters (events_udefs.c, vanilla Ch4 symbols):
    #    - UnitDef_Event_Ch4Ally: the deploy-cap TEMPLATE = THE CAP. NEVER LOADed; PREP reads
    #      its entry count (cap = cast_available_at(3), the 8 founding party + Baxby) and its
    #      YAML deploy_slots tiles, then redeploys the picks (cf. ch01/ch02 _deploy_cap_entries).
    #    - UnitDef_088B47E4 (boot only): the ARMED party seed -- the same field roster with real
    #      CLASS_LOADOUT kit, LOADed on --ch03-boot so PREP has a party to pick (ch03 has no
    #      prior chapter to found one yet). The real chain (item 3) omits it: the party persists.
    #    - UnitDef_088B49CC: Trex, GREEN in the galleries -- the vanilla Colm pattern (he stands
    #      unrecruited until a party member Talks to him -> CUSA join). Its own table so PREP's
    #      cap template stays the pure blue roster.
    #    - UnitDef_088B4A80: the 10 enemies (vanilla Ch3 parity) -- grell on the vanilla ch4
    #      boss slot, the kobolds/svirfneblin on the generic autolevelled slot.
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    for uid, _s, ce, _d, _l in cast:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch03 field roster %s)' % (ce, uid))
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    cap_rows = _deploy_cap_entries(chap, cast, leader, 'ch03')
    ally = '{\n' + '\n'.join(cap_rows) + '\n    { 0 },\n}'
    # Boot party seed: the field roster armed from CLASS_LOADOUT, on the deploy_slots tiles
    # (PREP hides + re-picks them, so the tiles only need to be legal). Built regardless; only
    # LOADed when boot (step 4). classIndex rides the deploy class (dce == the vanilla class).
    slots = chap['deployment']['deploy_slots']
    seed_rows = [_ally_unit_entry(leader, slot, dce, lv, x, y, ', '.join(CLASS_LOADOUT[ce]),
                                  ' /* %s -- boot party seed (armed; PREP re-picks) */' % uid)
                 for (uid, slot, ce, dce, lv), (x, y) in zip(cast, slots)]
    seed = '{\n' + '\n'.join(seed_rows) + '\n    { 0 },\n}'
    # Trex: the chapter's on-map recruit, placed GREEN (Colm-style) at the galleries. He is a
    # classed cast member (full cast, not available_at(3)); pull his slot/class from the roster.
    (trex_uid, tslot, _, tdce, tlv), = on_map_talk_recruits(campaign, chap['chapter_number'])
    tx, ty = CH03_TREX_GREEN_POS
    trex_green = '{\n' + _ally_unit_entry(
        leader, tslot, tdce, tlv, tx, ty, '0',
        ' /* trex -- green talk-recruit (Colm-style; CUSA on talk, #23 item 2) */',
        allegiance='GREEN') + '\n    { 0 },\n}'
    # Trex talk-recruit (#23 item 2): the shared talk-recruit wiring (talk_recruit_wiring, reused
    # by ch04/ch05). Recruiter set = ANY core party member (the ch03 field roster) -> ONE CHAR
    # entry each, all pointing at the shared recruit script (CUSA flips green Trex blue). FE8's
    # multi-recruiter idiom (cf. vanilla ch14a Rennac). No pre_script: Trex is a plain green recruit.
    trex_char = char_symbol(tslot)
    char_events, trex_talk_script = talk_recruit_wiring(
        talk_recruiters(campaign, chap['chapter_number']), trex_char,
        CH03_TREX_TALK_FLAG, CH03_TREX_TALK_SCRIPT, CH03_TREX_TALK_MSG)

    enemies = []
    for e in chap['enemy_units']:
        cls = CH03_CLASS_IDS[e.get('deploy_class') or e['class']]  # deploy_class = sprite-only override
        items = ', '.join(CH03_ITEM_IDS[i['id']] for i in e.get('inventory', []))
        drop = e.get('item_drop')
        if drop:
            items = '%s, %s' % (items, CH03_ITEM_IDS[drop]) if items else CH03_ITEM_IDS[drop]
        ai = CH03_AI.get(e.get('ai_pattern', 'defensive'), CH03_AI['defensive'])
        # The boss (grell) + the mid-map miniboss (Brute) each ride a UNIQUE raw pid so their
        # flagged gDefeatTalkList entries key their death events (WIN / midmap AFEV) to them
        # alone; every other enemy shares the generic autolevelled-trash pid.
        char = (CH03_BOSS_PID if e.get('is_boss')
                else CH03_BRUTE_MINIBOSS_PID if e.get('is_miniboss')
                else CH03_GENERIC_PID)
        for x, y in e['positions']:
            enemies.append(_enemy_unit_entry(
                char, cls, e['level'], bool(e.get('autolevel')), x, y, items, ai,
                ' /* %s */' % e['id'], itemdrop=bool(drop)))
    enemy = '{\n' + '\n'.join(enemies) + '\n    { 0 },\n}'

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(udefs, 'UnitDef_Event_Ch4Ally[] =', ally, EVENTS_UDEFS_C)
    udefs = _replace_brace_block(udefs, '%s[] =' % CH03_BOOT_SEED_SYMBOL, seed, EVENTS_UDEFS_C)
    udefs = _replace_brace_block(udefs, '%s[] =' % CH03_TREX_GREEN_SYMBOL, trex_green, EVENTS_UDEFS_C)
    udefs = _replace_brace_block(udefs, 'UnitDef_088B4A80[] =', enemy, EVENTS_UDEFS_C)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Strip cutscenes (cf. inject_test_chapter): empty the Ch4 event lists, wire the win/lose
    #    machinery into Misc (DefeatBoss on the grell's death + lord-death game-over), and make the
    #    beginning scene deploy the enemies + green Trex then run Preparations. DefeatBoss = AFEV on EVFLAG_DEFEAT_BOSS,
    #    which the grell's FLAGGED defeat quote sets on its death (step 5) -> runs the ending script;
    #    CauseGameOverIfLordDies = AFEV on EVFLAG_GAMEOVER (the lord's flagged quote / lord-select hook).
    with open(CH4_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    # Turn list: Trex's light entrance beat fires on turn 1 (player phase), the vanilla Colm
    # turn-1 green-NPC idiom (cf. inject_ch02's turn-1 tutorial TURN). Location stays empty.
    info = _replace_brace_block(
        info, 'EventListScr_Ch4_Turn[] =',
        '{\n    TURN(0x0, %s, 1, 0, FACTION_ID_BLUE)'
        ' /* turn-1: Trex\'s light entrance (Colm pattern) */\n    END_MAIN\n}'
        % CH03_TREX_ENTRANCE_SCRIPT, CH4_EVENTINFO_H)
    # Location = the mine chests + doors (#23). Each Chest(item, x, y) makes its tile openable
    # (IsThereClosedChestAt reads this list) and gives the item; each Door_(x, y) makes its tile a
    # thief/key door (TILE_COMMAND_DOOR, script=1 -> CallTileChangeEvent). The paired
    # MS_Ch03MapChanges entry (step 6b) flips the chest 17->29 on loot / the door to the floor tile
    # below it on open. Coords + items from the YAML (vanilla Ch3 Borgo 1:1; (8,3) = the Tourmaline,
    # the ch02<->ch03 swap).
    loc_events = '{\n' + ''.join(
        '    Chest(%s, %d, %d) /* %s */\n'
        % (CH03_ITEM_IDS[c['contents'][0]['id']], c['position'][0], c['position'][1],
           c['contents'][0]['id'])
        for c in chap['chests']) + ''.join(
        '    Door_(%d, %d)\n' % (d['position'][0], d['position'][1])
        for d in chap.get('doors', [])) + '    END_MAIN\n}'
    info = _replace_brace_block(info, 'EventListScr_Ch4_Location[] =', loc_events, CH4_EVENTINFO_H)
    # Character events = the Trex talk-recruit (#23 item 2): the CHAR-per-candidate list.
    info = _replace_brace_block(info, 'EventListScr_Ch4_Character[] =', char_events, CH4_EVENTINFO_H)
    # Misc = the win/lose machinery + the mid-map RBG-execution AFEV. DefeatBoss(ending) fires on
    # the grell's death (EVFLAG_DEFEAT_BOSS); the midmap AFEV fires ONCE on the Brute's death (its
    # flagged quote sets CH03_BRUTE_DEFEAT_FLAG), guarded by CH03_MIDMAP_GUARD_FLAG so it doesn't
    # re-run each turn -- the vanilla mid-map death-scene idiom (cf. ch1's tmp-flag AFEV).
    info = _replace_brace_block(
        info, 'EventListScr_Ch4_Misc[] =',
        '{\n    DefeatBoss(%s)\n    %s /* midmap: RBG executes the beaten Brute (#23) */\n'
        '    CauseGameOverIfLordDies\n    END_MAIN\n}'
        % (CH03_ENDING_SCRIPT,
           midmap_afev(CH03_MIDMAP_GUARD_FLAG, CH03_MIDMAP_SCRIPT, CH03_BRUTE_DEFEAT_FLAG)),
        CH4_EVENTINFO_H)
    # Ch4's tutorial list is an EventListScr[] (struct array), NOT the prologue's pointer
    # array -- so it terminates with END_MAIN, not NULL (NULL -> int-from-pointer error).
    info = _replace_brace_block(info, 'EventListScr_Ch4_Tutorial[] =', '{\n    END_MAIN\n}', CH4_EVENTINFO_H)
    with open(CH4_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # 3b. Tile-changes: pair each Chest()/Door_() location event above with a MapChange -- flips the
    #     FF5 navy chest 17->29 on loot, and each door to the floor tile below it on open (must run
    #     AFTER _retarget_host_chapter zeroed the slot's changeLayerId in step 1).
    _inject_ch03_tile_changes(chap, maps_dir, CH03_HOST_INDEX)

    with open(CH4_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    # Beginning scene = the vanilla prep-chapter shape (cf. inject_ch01/ch02) with a TWO-BG
    # opening (Nicolas 2026-07-09 staging): beats A-B play over the Termalaine STREET (crier +
    # bounty, then Wolfram's "we're going in"); on that line the BG CUTS to the mine interior --
    # empty, no portraits -- for the KOBOLDS ONLY sign, then Pinky scouts (he fades OUT into the
    # dark, an over-long tension pause holds on the empty cave, then he fades back in white-faced).
    # Then LOMA rebuilds the battle map fresh, the enemies + green Trex LOAD, and CALL Preparations
    # (PREP reads the never-LOADed cap template UnitDef_Event_Ch4Ally). --ch03-boot additionally
    # LOADs the armed party seed first, so PREP has a party from a cold New Game.
    labels = ['A -- the boy crier bawls the bounty; RBG takes the job (public mask up)',
              'B -- Wolfram scents the tourmaline seam; "We\'re going in"',
              'C -- the KOBOLDS ONLY sign (faceless #58 opaque box, empty cave)',
              'D -- Pinky scouts ahead (he fades out into the dark after this)',
              'E -- Pinky drops back white-faced; the grell looked at him']
    # Split the beat calls around the BG cut: A-B over the town, C-E inside the mine.
    town_calls = _scenic_beat_calls(CH03_OPENING_MSGS[:2], op_beats[:2], labels[:2])
    sign_call = _scenic_beat_calls(CH03_OPENING_MSGS[2:3], op_beats[2:3], labels[2:3])   # SOLOTEXTBOXSTART sign
    return_call = _scenic_beat_calls(CH03_OPENING_MSGS[4:5], op_beats[4:5], labels[4:5])  # Pinky returns
    # Beat D (Pinky scouts) is RAW TEXTSTART/SHOW/END -- NOT the Text() macro, whose trailing
    # REMA fades ALL portraits (why RBG used to vanish for the pause). No REMA here: RBG's face
    # persists (Pinky's own portrait fades at the beat's end via a trailing [ClearFace] in the
    # message body -- see CH03_OPENING_TRAILINGS). The over-long STAL(90) then holds on RBG alone
    # (he watches the dark; Nicolas 2026-07-10). Beat E's Text() re-opens with TEXTSTART, which
    # equals the still-active TEXTSTART type -> Event1A_TEXTSTART skips its face-clear, so RBG
    # carries through un-reloaded (TalkLoadFace early-returns on the occupied slot -- no reflicker)
    # while Pinky fades back in white-faced. Its trailing REMA then clears both into the FADI.
    scout_raw = ('    TEXTSTART\n'
                 '    TEXTSHOW(0x%X) /* %s */\n'
                 '    TEXTEND\n' % (CH03_OPENING_MSGS[3], labels[3]))
    seed_load = ('    LOAD1(0x1, %s) /* boot: found an armed party so PREP can pick (--ch03-boot) */\n'
                 '    ENUN\n' % CH03_BOOT_SEED_SYMBOL) if boot else ''
    begin = ('{\n'
             '    MUSC(SONG_TENSION)\n'
             '    REMOVEPORTRAITS\n'
             '    BACG(%s) /* Termalaine street (town BG) */\n'
             '    FADU(16)\n'
             '    BROWNBOXTEXT(0x%X, 8, 8) /* "Termalaine" location card */\n'
             % (CH03_OPENING_TOWN_BG, CH03_OPENING_CARD_MSG)
             + town_calls +
             '    REMA /* clear the town portraits before the cut */\n'
             '    FADI(16) /* fade the street out */\n'
             # BACG (EventShowTextBgDirect) only DECOMPRESSES a new BG when activeTextType is
             # REMOVEPORTRAITS/_1A22 (eventscr.c:1316) -- every other mode returns EVC_ERROR and
             # loads nothing. The town Text() beats above expand to TEXTSTART, which left
             # activeTextType == TEXTSTART, so a bare 2nd BACG was a no-op (stale town BG stayed
             # in VRAM). Re-arm the load mode first -- the vanilla multi-BG idiom (ch17a: every
             # BACG rides a REMOVEPORTRAITS-mode scene). Faded to black, so no visible pop.
             '    REMOVEPORTRAITS /* re-arm BACG BG-load mode (Text() beats reset it to TEXTSTART) */\n'
             '    BACG(%s) /* CUT to the mine interior -- empty, no PCs */\n'
             '    FADU(16)\n'
             % CH03_OPENING_MINE_BG
             + sign_call            # the KOBOLDS ONLY sign over the empty cave (#58 opaque box)
             + scout_raw +          # Pinky scouts: "I'll look ahead" / RBG / "Straight back!" (RAW, no REMA)
             '    STAL(90) /* over-long tension pause -- Pinky winged off, RBG holds at the mouth */\n'
             + return_call +        # Pinky fades back in, white-faced: "it looked at me" / RBG "Form up"
             '    FADI(16) /* fade the mine cutscene out */\n'
             '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
             '    LOMA(0x%X) /* RestartBattleMap -- build the ch03 map fresh (cf. inject_ch02) */\n'
             % CH03_HOST_INDEX
             + '    LOAD1(0x1, UnitDef_088B4A80) /* the vanilla-Ch3-parity enemies */\n    ENUN\n'
             + seed_load +
             '    LOAD1(0x1, %s) /* Trex -- green talk-recruit (Colm-style) */\n    ENUN\n'
             # NO FADU here: the shared prep prologue (EventScr_08591F64) fades to black itself
             # before drawing Preparations, so revealing the freshly-LOMA'd battle map first only
             # FLASHES it for a beat before prep blanks it again. Vanilla prep chapters (ch10a/ch13a)
             # go straight from the cutscene into CALL(prep) -- the map is first shown after Fight!,
             # never before prep. Stay black (the cutscene FADI above) straight into prep.
             '    CALL(%s) /* preparations (PREP, event cmd 0x3E) -- cap 9, lord force-deployed */\n'
             '    ENUT(8)\n'
             '    EVBIT_T(7)\n'
             '    ENDA\n}' % (CH03_TREX_GREEN_SYMBOL, CH03_PREP_SCRIPT))
    script = _replace_brace_block(script, 'EventScr_Ch4_BeginningScene[] =', begin, CH4_EVENTSCRIPT_H)
    # DefeatBoss ending (the script the Misc AFEV runs on the grell's death): victory sting ->
    # fade the mine out -> the ENDING cutscene over the reused Targos-winter BG (RBG takes the
    # bounty; Trex negotiates his warren into the town, which frees him to leave with the party;
    # Meesmickle's deadpan button) -> the dev-placeholder landing (RBG-by-the-campfire, then back
    # to title). ch04 isn't hosted yet, so the LANDING parks on the placeholder exactly as ch02's
    # ending does; the chaining pass (#23) swaps that dev landing for MNC2 -> ch04.
    end_text_calls = _scenic_beat_calls(
        CH03_ENDING_MSGS, end_beats,
        ['A -- RBG collects the Masthew bounty; the gems a "gratuity"',
         'B -- Trex negotiates his kobolds into the town, then asks to join the party',
         'C -- Meesmickle deadpan button (his one line of the chapter)'])
    ending = ('{\n    MUSC(SONG_VICTORY)\n'
              '    FADI(16) /* fade the mine out */\n'
              '    REMOVEPORTRAITS\n'
              '    BACG(%s) /* Termalaine square (reused Targos-winter BG) */\n'
              '    FADU(16)\n'
              '    BROWNBOXTEXT(0x%X, 8, 8) /* "Termalaine" location card */\n'
              % (CH03_ENDING_BG, CH03_ENDING_CARD_MSG)
              + end_text_calls +
              '    FADI(16) /* fade the square out into the dev-placeholder landing */\n'
              + dev_placeholder_scene() +
              '    ENDA\n}')
    script = _replace_brace_block(script, CH03_ENDING_SCRIPT + '[] =', ending, CH4_EVENTSCRIPT_H)
    # Trex's LIGHT entrance beat (Colm's turn-1 green-NPC pattern): a dead Ch4 Village script,
    # rewritten to show Pinky's telegraph ("He waved at me!") + RBG's warm "little dragon" over
    # the map. Fired by the turn-1 TURN entry (step 3). All of Trex's substance rides the TALK.
    script = _replace_brace_block(
        script, CH03_TREX_ENTRANCE_SCRIPT + '[] =',
        '{\n    TEXTSHOW(0x%X) /* Trex entrance: Pinky telegraph + RBG "little dragon" */\n'
        '    TEXTEND\n    REMA\n    EVBIT_T(7)\n    ENDA\n}' % CH03_TREX_ENTRANCE_MSG,
        CH4_EVENTSCRIPT_H)
    # Trex talk-recruit script (#23 item 2): repurpose the dead Ch4 Turn-2 green script symbol
    # -> show Trex's migrated talk line then CUSA green Trex to blue. Every CHAR entry (step 3)
    # points here, so ANY core party member's talk runs it (the vanilla Colm/Neimi shape).
    script = _replace_brace_block(script, CH03_TREX_TALK_SCRIPT + '[] =',
                                  trex_talk_script, CH4_EVENTSCRIPT_H)
    # Midmap RBG-execution beat (#23 item 1): the Misc AFEV runs this on the Brute's death. Plays
    # ON-MAP (no BACG -- the chapter continues on the same battle map). Each beat renders by whether
    # it has a face (_beat_is_faceless): FACED beats ride a map talk bubble via Text() (TEXTSTART..REMA
    # -- its trailing REMA clears the beat's faces, so none bleed into the next; a bare TEXTSHOW without
    # it left Pinky up under Wolfram). A speaker with no mug would ride the opaque AUTO-CENTERED box
    # (SOLOTEXTBOXSTART) -- a map bubble anchors to a speaking unit and an AFEV has none, so a faceless
    # bubble renders off the tilemap. All four midmap speakers now have mugs (the Brute got one on the
    # Caellach slot), so all four are faced bubbles here. EVBIT_T(7) marks the map event done.
    mid_labels = ['A -- Pinky reaches out to the beaten Brute (faced)',
                  'A2 -- ACTION: the Brute lunges at Pinky; claws ring off metal (faceless box)',
                  'A3 -- the Brute\'s shock: "you not soft?!" (faced mug)',
                  'B -- RBG levels the Fonduedler: "Say cheese." (faced)',
                  'B2 -- ACTION: the shot; the Brute drops dead (faceless box)',
                  'B3 -- Pinky "you saved me!" / RBG "always, my boy" (faced two-hander)',
                  'C -- Wolfram\'s oblivious ore gag deflates the moment (faced)']
    mid_calls = ''
    for msg, beat, lbl in zip(CH03_MIDMAP_MSGS, mid_beats, mid_labels):
        if _beat_is_faceless(beat, cut_fid):
            mid_calls += ('    SVAL(EVT_SLOT_B, 0xFF00FF) /* auto-center the opaque solo box (#58) */\n'
                          '    SOLOTEXTBOXSTART\n    TEXTSHOW(0x%X) /* %s */\n    TEXTEND\n    REMA\n'
                          % (msg, lbl))
        else:
            mid_calls += '    Text(0x%X) /* %s */\n' % (msg, lbl)
    script = _replace_brace_block(
        script, CH03_MIDMAP_SCRIPT + '[] =',
        '{\n' + mid_calls + '    EVBIT_T(7)\n    ENDA\n}', CH4_EVENTSCRIPT_H)
    with open(CH4_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 4. Texts: chapter title (status/prep banner). The grell's death quote was CUT (Nicolas): it
    #    has no portrait, so the faceless line rendered boxless + unreadable -- the DefeatBoss win now
    #    fires silently off the grell's flagged gDefeatTalkList entry (step 5, .msg = 0).
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    # The borrowed slot-6 defeat_boss goal block still points its Status-screen objective at
    # vanilla's "Defeat Saar" -- rewrite it as "Defeat <boss fe_name>" (the prologue precedent;
    # the goal WINDOW banner is a static "Defeat boss" by goal type, so only this text leaks).
    ch03_boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + (ch03_boss.get('fe_name') or ch03_boss['name'])))
    # Trex talk-recruit body (#23 item 2): his migrated pitch (chapter YAML talk_recruit event,
    # single source of truth), faced on the Rennac slot. One speaker -> one [OpenX] block with
    # page breaks; the recruit script (EventScr_089F199C) TEXTSHOWs it before the CUSA.
    talk = next(e for e in chap['events'] if e.get('trigger') == 'talk_recruit')['script']
    set_message_body(lines, CH03_TREX_TALK_MSG, _script_to_message(
        talk, {trex_uid: ('[OpenMidRight]', _fid_tag(tslot))}))
    # Cutscene beats (#23 Cutscenes): the opening + ending scenic beats over the Targos-winter BG
    # (location card + one message per beat, staged via _emit_scene_beats) and Trex's light on-map
    # entrance line (map-bubble wrap 29). Speakers resolve through cut_fid (cast busts + the crier
    # mug + faceless narration). RBG anchors mid-right in the opening + entrance (op_home).
    set_message_body(lines, CH03_OPENING_CARD_MSG, name_message_body(op_card))
    # Beat D (Pinky scouts, index 3) fades ONLY Pinky at its end so RBG holds through the STAL(90)
    # pause (Nicolas 2026-07-10). Pinky sits at the _stage_beat default podium ([OpenMidLeft] --
    # op_home anchors only prof-rbg, to [OpenMidRight]); the trailing [ClearFace] there fades his
    # portrait out, RBG's untouched. Pairs with scout_raw (no trailing REMA) in the event script.
    op_trailings = [None, None, None, '[OpenMidLeft][ClearFace]', None]
    _emit_scene_beats(lines, CH03_OPENING_MSGS, op_beats, cut_fid, op_home,
                      trailings=op_trailings)
    set_message_body(lines, CH03_ENDING_CARD_MSG, name_message_body(end_card))
    _emit_scene_beats(lines, CH03_ENDING_MSGS, end_beats, cut_fid, {})
    # Midmap RBG-execution beats (on-map, no card): faced beats wrap at the map-bubble 29; the two
    # faceless ACTION boxes wrap at 28 for the auto-centered opaque box. Beat A (Pinky's opening)
    # PRELOADS the Brute's mug as a silent listener at mid-right, so the player sees WHO Pinky is
    # talking to before it lunges (the Brute otherwise only appeared when it snarled in A3 -- Nicolas
    # 2026-07-11). The Brute + RBG both anchor mid-right via op_home (never on screen together; each
    # beat's REMA clears faces); Pinky/party default mid-left.
    brute_face = cut_fid('kobold-brute')   # [FID_Caellach] -- the Brute's mug slot
    mid_preloads = [[('[OpenMidRight]', brute_face)]] + [None] * (len(mid_beats) - 1)
    for msg, beat, preload in zip(CH03_MIDMAP_MSGS, mid_beats, mid_preloads):
        w = 28 if _beat_is_faceless(beat, cut_fid) else 29
        set_message_body(lines, msg, _script_to_message(
            beat, _stage_beat(beat, cut_fid, op_home), width=w, preload=preload))
    set_message_body(lines, CH03_TREX_ENTRANCE_MSG, _script_to_message(
        trex_entr, _stage_beat(trex_entr, cut_fid, op_home), width=29))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    # 4a. Title card image (the intro/status banner is a 4bpp image, not text) -- "Ch.3:
    #     <title>" composed from vanilla glyphs, overwriting the host slot's vanilla card
    #     (chapTitleId 4 = the "Ch.4: Ancient Horrors" card). gen_chapter_title reads the
    #     source cards from HEAD, so overwriting chap_title_4.png here doesn't disturb any cut.
    _write_chapter_title_card(host, 'Ch.3: ' + chap['title'])

    # 5. The grell's flagged gDefeatTalkList entry keys the DefeatBoss win to its raw pid (first-match
    #    scan wins; no vanilla 0xb7 entry to shadow). .flag = EVFLAG_DEFEAT_BOSS is what fires the win.
    #    .msg = 0: NO death quote (the grell has no portrait, so the faceless line rendered boxless +
    #    unreadable; Nicolas cut it). The engine still sets the flag -- DisplayDefeatTalkForPid only
    #    shows the quote `if (ent->msg != 0)` but SetPidDefeatedFlag runs regardless (eventinfo.c:595).
    #    The Brute miniboss rides the SAME silent-quote idiom: its flagged death sets the tmp flag
    #    CH03_BRUTE_DEFEAT_FLAG that the mid-map RBG-execution AFEV watches (step 3). Different pids
    #    -> both entries coexist at the head; the first-match pid scan keys each to its own unit.
    _prepend_defeat_quote(flag_defeat_quote(
        CH03_BOSS_PID, 'CHAPTER_L_4', 'EVFLAG_DEFEAT_BOSS',
        'grell (ch03 boss): silent defeat -> DefeatBoss WIN flag'))
    _prepend_defeat_quote(flag_defeat_quote(
        CH03_BRUTE_MINIBOSS_PID, 'CHAPTER_L_4', CH03_BRUTE_DEFEAT_FLAG,
        'Icewind Brute (ch03 miniboss): silent defeat -> mid-map RBG-execution AFEV'))

    if verbose:
        print('  ch03 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; defeat_boss goal + '
              'DefeatBoss(grell) WIN wired, PREP deploy cap %d%s + %d enemies (grell@14,1); opening/entrance/midmap/ending cutscenes wired'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH03_HOST_INDEX, len(cap_rows),
                 ' (boot-seeded party)' if boot else '', len(enemies)))


def inject_ch04(campaign, boot=False, verbose=True):
    """Host Ch4 "The White Moose" (#24) on slot 5 with its approved snowy map and
    vanilla-named monster force: fog, PREP/deployment, 10 line enemies, the turn-2
    wolf-pack reveal (6) and turn-3 reinforcements (7), Rout, and a direct debug boot.

    Stage 2b wires the Marty->Lupin PARLEY (the pack leader is Lupin, placed red among the
    turn-2 wave; Marty's Talk CUSNs each SURVIVING generic Mauthe Doog green where it stands
    and CUSAs Lupin blue -- the shared talk-recruit flow, reused from ch03). Stage 2c wires
    the turn-2 REVEAL cutscene (rides the turn-2 LOAD1: pan to the NW fog, focus Lupin, stub
    beats plant the parley).

    Stage 4 wires the AUTHORED SCENES, all off the locked chapter YAML:
      * the LONELYWOOD OPENING -- a two-BG scene (Nimsy's cottage over vanilla House1, cut to
        the fogged forest edge for Pinky's fog-of-war heads-up), then LOMA + prep;
      * the full five-turn PARLEY text (was a one-line stub of its closing beat);
      * the MOOSE-FLEES beat -- a Misc AREA over the tomb-side clearing loads the quarry, holds
        on it, and bolts it off the NE edge (it never speaks: locked mute in ch04 and ch05);
      * the REAL ENDING, replacing dev_placeholder_scene() -- and BRANCHED, because Lupin's
        recruit is optional: CHECK_EVENTID on the parley flag picks between the locked scene and
        the no-Lupin variant whose boxes 1/3 go to Pinky and Meesmickle.
    The reveal cutscene's own two beats are still stubs pending a dialogue-pass.

    Run after inject_ch03 in campaign order. After both hosts are injected,
    chain_ch03_to_ch04 advances the real campaign path.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH04_CHAPTER_YAML)

    # 0. Stage 4 -- the authored scenes, split out of the locked chapter YAML (cf. inject_ch03).
    #    The opening splits on its one beat_break (A the cottage / B the forest edge); the moose
    #    beat and the ending carry no location_card, so card_required=False.
    op_card, op_beats = _split_event_beats(chap, 'chapter_start', 'ch04 opening',
                                           CH04_OPENING_MSGS)
    _, moose_beats = _split_event_beats(chap, 'moose_sighted', 'ch04 moose-flees',
                                        (CH04_MOOSE_MSG,), card_required=False)
    _, end_beats = _split_event_beats(chap, 'chapter_end', 'ch04 ending',
                                      (CH04_ENDING_MSG,), card_required=False)
    # The no-Lupin branch: the SAME scene with boxes 1 and 3 swapped (Marty's box 2 rides through
    # unchanged). Anchored to the text it replaces, so a re-ordered locked script fails loudly
    # rather than silently mis-swapping -- see variant_beat.
    end_event = next(e for e in chap['events'] if e.get('trigger') == 'chapter_end')
    end_beat_no_lupin = variant_beat(end_beats[0], end_event['no_lupin_fallback'],
                                     'ch04 ending no-Lupin fallback')
    # Speaker -> face. Nimsy rides the VANILLA old-lady generic mug (Nicolas 2026-07-04: it ships
    # in the base ROM, so no vendored asset and no credit line); everyone else is cast.
    cut_fid = _make_fid({'nimsy': CH04_NIMSY_FID}, 'ch04 unknown cutscene speaker')
    # Podiums for the cottage scene. RBG opens it and Nimsy answers him, so BOTH are anchored --
    # she to her own podium, not the shared mid-left. Without that she is the only speaker who
    # alternates with the party (RBG -> Nimsy -> Marty -> Nimsy -> Meesmickle), and the LRU
    # podium manager fades her out and back in twice: the quest-giver flickers through her own
    # scene. Four distinct podiums = the face budget exactly, so nothing is evicted.
    op_home = {'prof-rbg': '[OpenMidRight]', 'nimsy': '[OpenFarRight]',
               'meesmickle': '[OpenFarLeft]'}

    indices = _register_chapter_map(
        maps_dir, CH04_LAYOUT, 'Manchego Stars ch04 Lonelywood forest layout (#24)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH04_HOST_INDEX, CH04_GOAL_DONOR, 'defeat_all',
        'ERROR: hosted ch02 slot %d is not the stable defeat_all goal donor for ch04'
        % CH04_GOAL_DONOR,
        indices, chap['chapter_number'], CH04_EVENT_GROUP,
        (CH04_GOAL_WINDOW_MSG, CH04_GOAL_STATUS_MSG))

    # Fog is chapter state, not painted-map data. Battle terrain 0x15 is the shared
    # snowy rough platform family already used by the winter overworld chapters.
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    settings['chapters'][CH04_HOST_INDEX]['initialFogLevel'] = 3
    settings['chapters'][CH04_HOST_INDEX]['battleTileSet'] = 0x15
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    for uid, _slot, ce, _dce, _level in cast:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch04 field roster %s)' % (ce, uid))
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    cap_rows = _deploy_cap_entries(chap, cast, leader, 'ch04')
    ally = '{\n' + '\n'.join(cap_rows) + '\n    { 0 },\n}'

    slots = chap['deployment']['deploy_slots']
    seed_rows = [_ally_unit_entry(
        leader, slot, dce, level, x, y, ', '.join(CLASS_LOADOUT[ce]),
        ' /* %s -- ch04 boot party seed (armed; PREP re-picks) */' % uid)
        for (uid, slot, ce, dce, level), (x, y) in zip(cast, slots)]
    seed = '{\n' + '\n'.join(seed_rows) + '\n    { 0 },\n}'

    initial_rows = ch04_enemy_rows(chap)
    turn3_rows = ch04_enemy_rows(chap, arrives_turn=3)
    # Stage 2b -- the turn-2 wolf-pack reveal: the convertible Mauthe Doog wave with its leader
    # tile reassigned to Lupin (red, CHARACTER_DUESSEL). 5 generic Mauthe Doogs + Lupin = 6, so
    # ch04_enemy_rows still reports 6 for the difficulty read (parity held); the split is here.
    lupin = next(r for r in on_map_talk_recruits(campaign, chap['chapter_number'])
                 if r[0] == 'lupin')
    turn2_rows = ch04_turn2_reveal_rows(chap, lupin)
    if [len(initial_rows), len(ch04_enemy_rows(chap, arrives_turn=2)),
            len(turn3_rows)] != [10, 6, 7]:
        sys.exit('ERROR: ch04 realigned roster must stay 10 line + 6 turn-2 reveal + 7 turn-3')

    def table(rows):
        return '{\n' + '\n'.join(rows) + '\n    { 0 },\n}'

    # The white moose: a lone scripted NEUTRAL (green), on its own pid so the flee beat's DISA
    # can only ever take it. Its Wyrdeer map sprite rides the cast palette via gMapPaletteOverride
    # (it never changes faction) -- see the chapter YAML's `art:` block.
    mx, my = CH04_MOOSE_POS
    moose_row = _ally_unit_entry(
        None, 'white-moose', CH04_MOOSE_CLASS, 1, mx, my, '0',
        ' /* the white moose -- scripted quarry, never fought (canon: uncatchable) */',
        allegiance='GREEN', char=CH04_MOOSE_PID)
    # Its authored bridge route has to be WALKABLE or MOVE_DEFINED + ENUN hangs the chapter.
    moose_data = next(u for u in chap['neutral_units'] if u['id'] == 'white-moose')
    moose_camera = tuple(moose_data['camera_at'])
    moose_route = tuple(tuple(point) for point in moose_data['flee_route'])
    for waypoint in moose_route:
        assert_scripted_move_reachable(maps_dir, CH04_LAYOUT[1], CH04_MOOSE_POS,
                                       waypoint, CH04_MOOSE_MOV_TABLE, 'the white moose')

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    for symbol, body in (
            ('UnitDef_Event_Ch5Ally', ally),
            (CH04_INITIAL_ENEMY_SYMBOL, table(initial_rows)),
            (CH04_TURN2_SYMBOL, table(turn2_rows)),
            (CH04_TURN3_SYMBOL, table(turn3_rows)),
            (CH04_MOOSE_SYMBOL, table([moose_row])),
            (CH04_BOOT_SEED_SYMBOL, seed)):
        udefs = _replace_brace_block(udefs, symbol + '[] =', body, EVENTS_UDEFS_C)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # The Marty->Lupin parley (Stage 2b): the shared talk-recruit wiring (talk_recruit_wiring),
    # recruiter = Marty ONLY (parley_recruiters, data-driven from parley.by; Nicolas
    # 2026-07-21). The talk script's pre_script turns the pack GREEN WHERE IT STANDS -- one
    # CHECK_ALIVE-guarded CUSN per wolf (#203) -- then CUSA flips Lupin blue. One flow with
    # ch03's green Trex; the parley IS the recruit. Because CUSN can only convert wolves that
    # are still alive, the ally count scales with survivors: talking EARLY is the reward.
    parley_pre = convert_survivors_green(
        CH04_PACK_PIDS, CH04_PARLEY_LABEL_BASE, 'Mauthe Doog')
    assert_pack_pids_addressable(chap, CH04_PACK_PIDS)   # #198 review guard, re-aimed by #203
    recruiters = parley_recruiters(_ch04_reveal_wave(chap))
    lupin_char_events, lupin_talk_script = talk_recruit_wiring(
        recruiters, char_symbol(lupin[1]),
        CH04_LUPIN_TALK_FLAG, CH04_LUPIN_TALK_SCRIPT, CH04_LUPIN_TALK_MSG,
        pre_script=parley_pre)
    # Force-deploy the parley recruiter(s): the parley is gated on Marty specifically (unlike
    # ch03's any-party-member talk), so benching Marty would miss the recruit. Field him via
    # vanilla's per-chapter ForceDeploymentEnt data path -- no new engine code (harmless if the
    # player chose Marty as lord: the lord check already force-deploys him). Nicolas 2026-07-21.
    # ch05 needs no counterpart: its gated recruiter (Basil) is not on the prep roster at all --
    # she is LOADed onto the map by the beginning scene, so there is no Pick Units to bench her.
    _force_deploy_units(recruiters, CH04_HOST_INDEX)

    with open(CH5_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    info = _replace_brace_block(
        info, 'EventListScr_Ch5_Turn[] =',
        '{\n    TurnEventPlayer(0, EventScr_089F22A4, 2)'
        ' /* turn-2 reveal: 5 Mauthe Doogs + Lupin (red pack leader) */\n'
        '    TurnEventPlayer(0, EventScr_089F22EC, 3) /* turn-3 reinf: revenant + bonewalker packs */\n'
        '    END_MAIN\n}', CH5_EVENTINFO_H)
    # Character = the Marty->Lupin parley CHAR list (Stage 2b); the rest stay empty.
    info = _replace_brace_block(info, 'EventListScr_Ch5_Character[] =',
                                lupin_char_events, CH5_EVENTINFO_H)
    # Location = the villages (#205). Vanilla Ch4's Location list is two `Village` entries; ours
    # keeps the ITEM one at the same tile (the parley took the recruit one's job). Blanking this
    # list is what made ch04's Iron Axe unobtainable -- and the map's door tile had ALSO lost its
    # village terrain in the reskin, so both halves had to come back.
    assert_village_tiles_visitable(chap, maps_dir, CH04_LAYOUT[1])
    # No-op today -- ch04's forest is a from-scratch canvas, so its `map:` block names no
    # `vanilla_layout:` and there is no vanilla gift placement to inherit. Wired anyway so the
    # rule travels with the chapter rather than with whoever remembers it (#25).
    assert_village_gifts_match_vanilla(chap, CH04_ITEM_IDS)
    info = _replace_brace_block(info, 'EventListScr_Ch5_Location[] =',
                                ch04_location_events(chap), CH5_EVENTINFO_H)
    # Tile flips (#214): the snag falls into a crossing (the Iron Axe's whole purpose) and each
    # visited village closes its door. Must run AFTER _retarget_host_chapter zeroed changeLayerId.
    _inject_tile_changes('MS_Ch04MapChanges', ch04_map_changes(chap, maps_dir), CH04_HOST_INDEX)
    for symbol in ('EventListScr_Ch5_SelectUnit', 'EventListScr_Ch5_SelectDestination',
                   'EventListScr_Ch5_UnitMove', 'EventListScr_Ch5_Tutorial'):
        info = _replace_brace_block(info, symbol + '[] =',
                                    '{\n    END_MAIN\n}', CH5_EVENTINFO_H)
    # Misc = win/lose + the moose sighting. AREA fires once when a player unit steps into the
    # tomb-side clearing (guarded by its own tmp flag, the vanilla one-shot idiom, cf. ch1's
    # AREA) -- the quarry is seen and lost in the same beat.
    mx1, my1, mx2, my2 = CH04_MOOSE_AREA
    info = _replace_brace_block(
        info, 'EventListScr_Ch5_Misc[] =',
        '{\n    DefeatAll(%s)\n'
        '    AREA(%s, %s, %d, %d, %d, %d) /* the white moose is sighted, and bolts */\n'
        '    CauseGameOverIfLordDies\n    END_MAIN\n}'
        % (CH04_ENDING_SCRIPT, CH04_MOOSE_GUARD_FLAG, CH04_MOOSE_SCRIPT,
           mx1, my1, mx2, my2), CH5_EVENTINFO_H)
    with open(CH5_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    with open(CH5_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    seed_load = ('    LOAD1(0x1, %s) /* --ch04-boot: found an armed party */\n'
                 '    ENUN\n' % CH04_BOOT_SEED_SYMBOL) if boot else ''
    # Stage 4 -- the LONELYWOOD OPENING, a two-BG scene (the ch03 shape). Beat A plays in
    # Speaker Nimsy Huddle's cottage over vanilla's House1 hearth; the deaf-Speaker gag resolves
    # through Marty's rapport spores and Meesmickle takes the job. Then the BG CUTS to the forest
    # edge for beat B, where Pinky's line delivers the fog-of-war heads-up (onboarding parity, in
    # voice) and buttons into gameplay. Both beats are LOCKED (dialogue-pass, 2026-07-03).
    op_calls_a = _scenic_beat_calls(CH04_OPENING_MSGS[:1], op_beats[:1],
                                    ['A -- Nimsy\'s cottage: the moose problem; Marty\'s spores '
                                     'cut through the deafness; Meesmickle takes the job'])
    op_calls_b = _scenic_beat_calls(CH04_OPENING_MSGS[1:], op_beats[1:],
                                    ['B -- the forest edge: Pinky flew up and the fog looked back '
                                     '(introduces: fog-of-war)'])
    beginning = ('{\n'
                 '    MUSC(SONG_TENSION)\n'
                 '    REMOVEPORTRAITS\n'
                 '    BACG(%s) /* Nimsy Huddle\'s cottage -- vanilla House1 hearth interior */\n'
                 '    FADU(16)\n'
                 '    BROWNBOXTEXT(0x%X, 8, 8) /* "Lonelywood" location card */\n'
                 % (CH04_OPENING_COTTAGE_BG, CH04_OPENING_CARD_MSG)
                 + op_calls_a +
                 '    REMA /* clear the cottage portraits before the cut */\n'
                 '    FADI(16)\n'
                 # BACG only decompresses a new BG while activeTextType is REMOVEPORTRAITS/_1A22
                 # (eventscr.c:1316); the Text() beats above left it at TEXTSTART, so a bare second
                 # BACG would be a no-op and the cottage would stay in VRAM. Re-arm the load mode
                 # first -- the vanilla multi-BG idiom, and exactly the ch03 opening's fix.
                 '    REMOVEPORTRAITS /* re-arm BACG BG-load mode (Text() reset it to TEXTSTART) */\n'
                 '    BACG(%s) /* CUT to the forest edge, fog hanging between the trees */\n'
                 '    FADU(16)\n' % CH04_OPENING_FOREST_BG
                 + op_calls_b +
                 '    FADI(16) /* fade the forest edge out */\n'
                 '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
                 '    LOMA(0x%X) /* RestartBattleMap -- build the ch04 map fresh (cf. inject_ch03) */\n'
                 % CH04_HOST_INDEX
                 + '    LOAD1(0x1, %s) /* approved turn-1 force: 10 monsters (reveal opens monsters-only) */\n'
                   '    ENUN\n' % CH04_INITIAL_ENEMY_SYMBOL
                 + seed_load +
                 # NO FADU: the shared prep prologue fades to black itself before drawing
                 # Preparations, so revealing the freshly-LOMA'd map here only flashes it.
                 '    CALL(%s) /* preparations: pick 9 of 10; lord force-deployed */\n'
                 '    ENUT(8)\n'
                 '    EVBIT_T(7)\n'
                 '    ENDA\n}' % CH04_PREP_SCRIPT)
    script = _replace_brace_block(
        script, 'EventScr_Ch5_BeginningScene[] =', beginning, CH5_EVENTSCRIPT_H)
    # Turn-2 REVEAL cutscene (Stage 2c): the same TurnEvent script that LOADs the reveal wave
    # now also stages it -- camera to the NW fog, focus Lupin, stub beats plant the parley.
    script = _replace_brace_block(
        script, CH04_REVEAL_SCRIPT + '[] =',
        ch04_reveal_cutscene_script(CH04_TURN2_SYMBOL, char_symbol(lupin[1]),
                                    CH04_REVEAL_MSGS, CH04_REVEAL_CAMERA),
        CH5_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_089F22EC[] =',
        '{\n    LOAD1(0x1, %s)\n    ENUN\n    ENDA\n}' % CH04_TURN3_SYMBOL,
        CH5_EVENTSCRIPT_H)
    # The Marty->Lupin parley script (Stage 2b): repurpose a dead Ch5 script -> convert the
    # surviving pack green in place, then CUSA Lupin blue (built above).
    script = _replace_brace_block(
        script, CH04_LUPIN_TALK_SCRIPT + '[] =', lupin_talk_script, CH5_EVENTSCRIPT_H)
    # The village visits (#205, #24): vanilla Ch4's own give-an-item shape, with the line and the
    # reward read from the chapter YAML. One script per door -- the axe village hands the Iron Axe
    # over, the forest cottage pays in lore alone (Ch4-lean economy).
    for village in chap['villages']:
        symbol, msg, _fid, bg = CH04_VILLAGE_SLOTS[village['id']]
        script = _replace_brace_block(
            script, symbol + '[] =',
            village_script(msg, village_reward_item(village, CH04_ITEM_IDS), bg),
            CH5_EVENTSCRIPT_H)
    # The moose-flees beat (Stage 4): fired by the Misc AREA when a unit reaches the tomb-side
    # clearing. Loads the moose, holds on it, RBG's one line, then it bolts NE and is gone.
    script = _replace_brace_block(
        script, CH04_MOOSE_SCRIPT + '[] =',
        ch04_moose_script(CH04_MOOSE_SYMBOL, CH04_MOOSE_PID, CH04_MOOSE_MSG,
                          moose_camera, moose_route), CH5_EVENTSCRIPT_H)
    # The REAL ENDING (Stage 4), replacing the dev-placeholder landing: dusk at the treeline, the
    # pack in harness beside Baxby, Lupin noses the moose's trail to the tomb door and drops the
    # chapter's one Ravisin seed. Then MNC2 onward -- ch05 is not hosted yet, so it still lands on
    # the dev placeholder, exactly as ch03's ending did until ch04 hosted.
    #
    # BRANCHED on the parley flag: Lupin's recruit is gated on Marty's Talk, and the difficulty
    # model explicitly prices a no-parley clear -- so on that path two of this scene's three boxes
    # have no speaker, including the chapter's closing button. CHECK_EVENTID on the recruit flag
    # picks the variant (branch_on_flag; the vanilla ch19a-ending idiom). Plays over a BG rather
    # than on-map ON PURPOSE: a faced on-map beat rides a talk bubble anchored to a speaking UNIT,
    # and with deploy 9-of-10 the fallback's speakers (Pinky, Meesmickle) can be benched -- over a
    # BG the full-screen window needs no anchor.
    end_scene = (
        '    REMOVEPORTRAITS\n'
        '    BACG(%s) /* dusk at the treeline; the sled at the ridge */\n'
        '    FADU(16)\n' % CH04_ENDING_BG)
    ending = ('{\n    MUSC(SONG_VICTORY)\n'
              '    FADI(16) /* fade the forest out */\n'
              + end_scene
              + branch_on_flag(
                  CH04_LUPIN_TALK_FLAG,
                  '    Text(0x%X) /* parleyed: Lupin reads the trail + the Ravisin seed */\n'
                  % CH04_ENDING_MSG,
                  '    Text(0x%X) /* no parley: Pinky reads the trail, Meesmickle takes the dread */\n'
                  % CH04_ENDING_NO_LUPIN_MSG)
              + '    FADI(16) /* fade the treeline out into the dev-placeholder landing */\n'
              + dev_placeholder_scene()
              + '    ENDA\n}')
    script = _replace_brace_block(
        script, CH04_ENDING_SCRIPT + '[] =', ending, CH5_EVENTSCRIPT_H)
    with open(CH5_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    # Vanilla's own wording (see the ch02 note): FE8 prints "Defeat", never "rout". ch04 owns
    # both strings now (#207) -- it used to write only the status line and inherit ch02's window,
    # which is precisely the sharing that made the two chapters overwrite each other.
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat all monsters'))
    set_message_body(lines, host['goal']['windowTextId'],
                     goal_window_body('Defeat enemy'))
    # Stage 4 -- the FULL locked parley (was a one-line stub of its closing beat). Five turns,
    # Lupin/Marty alternating: the count-off, Marty's spore-puff opener, the BIRD retort, the
    # goodberry pack-math, and Lupin doing the arithmetic out loud. Marty sits mid-left (party
    # side), Lupin mid-right (pack side), so the exchange stages as a two-shot.
    talk = next(e for e in chap['events'] if e.get('trigger') == 'unit_reaches_zone')['script']
    set_message_body(lines, CH04_LUPIN_TALK_MSG, _script_to_message(
        talk, {'lupin': ('[OpenMidRight]', _fid_tag(lupin[1])),
               'marty': ('[OpenMidLeft]', _fid_tag(PORTRAIT_MAP['marty']))}))
    # Turn-2 reveal cutscene beats -- LOCKED text, read from the chapter YAML like every other
    # ch04 scene (#208; they were Python literals left over from the Stage 2c stubs). Lupin
    # commands the pack from the pack side (mid-right); Marty reads it cross-field from the party
    # side (mid-left) and FLAGS the parley -- the beat that teaches "talk to the leader".
    # ON-MAP, so it wraps at the map-bubble 29 like the moose beat, not the BG scenes' 42.
    _, reveal_beats = _split_event_beats(chap, 'wolf_pack_reveal', 'ch04 turn-2 reveal',
                                         msg_ids=CH04_REVEAL_MSGS, card_required=False)
    _emit_scene_beats(lines, CH04_REVEAL_MSGS, reveal_beats, cut_fid,
                      {'lupin': '[OpenMidRight]', 'marty': '[OpenMidLeft]'}, width=29)
    # Stage 4 scene bodies. The opening + both endings play over a BG (full-screen window, wrap
    # 42); the moose beat is ON-MAP, so it wraps at the map-bubble 29 (a wider line hits
    # PutTalkBubble's unclamped right-side branch and runs off the tilemap -- the ch03 crier bug).
    set_message_body(lines, CH04_OPENING_CARD_MSG, name_message_body(op_card))
    _emit_scene_beats(lines, CH04_OPENING_MSGS, op_beats, cut_fid, op_home, width=42)
    _emit_scene_beats(lines, (CH04_MOOSE_MSG,), moose_beats, cut_fid, {}, width=29)
    # Both endings stage as a two-shot: the trail-reader holds mid-right, Marty answers from
    # mid-left. Lupin already owns mid-right in the parley, so he keeps it here; on the no-parley
    # path PINKY inherits both the podium and the job (his opening beat was failing to see
    # through the fog, so finding the trail once it thins pays that off). Without these anchors
    # every box defaults to mid-left and each speaker fades the last one out mid-scene.
    end_home = {'lupin': '[OpenMidRight]', 'pinky': '[OpenMidRight]',
                'meesmickle': '[OpenFarLeft]'}
    _emit_scene_beats(lines, (CH04_ENDING_MSG,), end_beats, cut_fid, end_home, width=42)
    _emit_scene_beats(lines, (CH04_ENDING_NO_LUPIN_MSG,), [end_beat_no_lupin],
                      cut_fid, end_home, width=42)
    # The village lines (#205, #24). The axe door is Nimsy herself, wearing the vanilla old-lady
    # mug the opening already gave her; the forest cottage is a logger who never opens up, on
    # vanilla's own snag-village mug. Both play over BG_NORMAL_VILLAGE (full-screen window), so
    # they wrap at 42 like the other BG scenes rather than the on-map bubble's 29.
    #
    # One `visit_text` entry per BOX: consecutive turns by one speaker coalesce into a single
    # [OpenX] block with each entry's pages kept whole, so the authored beats survive as the
    # A-press breaks instead of being reflowed into wherever 42 columns happen to land.
    for village in chap['villages']:
        _symbol, msg, fid, _bg = CH04_VILLAGE_SLOTS[village['id']]
        set_message_body(lines, msg, _script_to_message(
            [{'villager': box} for box in village_boxes(village)],
            {'villager': ('[OpenMidLeft]', fid)}, width=42))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    _write_chapter_title_card(host, 'Ch.4: ' + chap['title'])

    if verbose:
        print('  ch04 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'fog 3, DefeatAll, PREP cap %d%s, enemies 10 + 6(t2 reveal: 5 Doog + red Lupin) + 7(t3); '
              'turn-2 reveal cutscene + Marty->Lupin parley (%d guarded CUSN in place + CUSA)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH04_HOST_INDEX, len(cap_rows),
                 ' (boot-seeded party)' if boot else '', len(CH04_PACK_PIDS)))
        print('  ch04 scenes: opening (2 BGs, %d+%d lines) + full parley (%d) + moose-flees '
              '(AREA %d,%d..%d,%d) + ending (%d boxes, branched: Lupin / no-parley)'
              % (len(op_beats[0]), len(op_beats[1]), len(talk), mx1, my1, mx2, my2,
                 len(end_beats[0])))


def ch05_enemy_rows(chap, arrives_turn=None, exclude=()):
    """One UnitDefinition row per authored position for a ch05 deployment wave.

    `arrives_turn=None` selects the turn-1 line; a number selects that reinforcement wave.
    `exclude` drops enemies by id (Sahnar rides turn 2 but LOADs from her own table, so the
    wake beat can address her alone). The boss and the moose each take a unique pid so their
    gDefeatTalkList entries key to them and nothing else; everything else is generic trash.
    """
    rows = []
    for enemy in chap['enemy_units']:
        if enemy.get('arrives_turn') != arrives_turn or enemy['id'] in exclude:
            continue
        cls = CH05_CLASS_IDS[enemy.get('deploy_class') or enemy['class']]
        items = [CH05_ITEM_IDS[item.get('fe_base') or item['id']]
                 for item in enemy.get('inventory', [])]
        drop = enemy.get('item_drop')
        ai = CH05_AI[enemy.get('ai_pattern', 'defensive')]
        pid = (CH05_BOSS_PID if enemy.get('is_boss')
               else CH05_MOOSE_PID if enemy.get('is_miniboss')
               else CH05_GENERIC_PID)
        for index, (x, y) in enumerate(enemy['positions']):
            carried = list(items)
            dropper = bool(drop) and index == 0
            if dropper:
                carried.append(CH05_ITEM_IDS[drop])
            rows.append(_enemy_unit_entry(
                pid, cls, int(enemy['level']), bool(enemy.get('autolevel')), x, y,
                ', '.join(carried) or '0', ai,
                ' /* %s -- %s */' % (enemy['id'], enemy['name']), itemdrop=dropper))
    return rows


def ch05_eruption_message(chap):
    """Render the locked turn-2 Ravisin warning from the chapter YAML.

    The YAML's ``vanilla 0x9C5`` label is an anatomy citation, not a destination: ch04
    writes that literal id. The caller stores this body at CH05_ERUPTION_MSG, which belongs
    to the Ch6 host block ch05 actually owns.
    """
    _card, beats = _split_event_beats(
        chap, 'eruption_turn', 'ch05 eruption warning', (CH05_ERUPTION_MSG,),
        card_required=False)
    beat = beats[0]
    speakers = {next(iter(entry)) for entry in beat}
    if len(beat) != 4 or speakers != {'ravisin'}:
        sys.exit('ERROR: ch05 eruption warning must remain the four locked Ravisin boxes; '
                 'got %d boxes from %s' % (len(beat), sorted(speakers)))
    return _script_to_message(
        beat,
        {'ravisin': ('[OpenMidLeft]', _fid_tag(GUEST_PORTRAIT_MAP['ravisin']))},
        width=29)


def ch05_wave_script(turn, wave_table, sahnar_table=None):
    """Build one ch05 reinforcement script; only turn 2 speaks and wakes Sahnar.

    The order carries the fiction: the arriving dead establish the escalation, Ravisin names
    the reliquary race and decides to spend the blade under the stone, then Sahnar LOADs.
    Later waves are silent reinforcements and must not replay the warning.
    """
    warning = ''
    wake = ''
    if turn == 2:
        if not sahnar_table:
            sys.exit('ERROR: ch05 turn-2 wave needs Sahnar\'s wake table')
        warning = (
            '    CUMO_CHAR(%s) /* Ravisin answers the party\'s pressure */\n'
            '    STAL(45)\n'
            '    CURE\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X) /* four locked boxes: the reliquary race + Sahnar */\n'
            '    TEXTEND\n'
            '    REMA\n'
            % (CH05_BOSS_PID, CH05_ERUPTION_MSG))
        wake = (
            '    LOAD1(0x1, %s) /* Sahnar rises from the cracked sarcophagus */\n'
            '    ENUN\n' % sahnar_table)
    elif sahnar_table is not None:
        sys.exit('ERROR: ch05 Sahnar may rise only in the turn-2 eruption script')
    return ('{\n'
            '    LOAD1(0x1, %s)\n'
            '    ENUN\n'
            '%s%s'
            '    ENDA\n}' % (wave_table, warning, wake))


def inject_ch05(campaign, boot=False, verbose=True):
    """Host Ch5 "The Elven Tomb" (#25) on slot 6: the winterised 1:1 retile of vanilla Ch5,
    the sixteen-strong risen tomb-guard on vanilla Ch5's own fighting tiles, the three
    eruption waves on its raider spawns, the real PREP deploy, and DefeatBoss(Ravisin).

    EVERYTHING that is content is mined from vanilla FE8 Ch5, which this chapter is the 1:1
    twin of -- geometry, terrain (drift 0), all sixteen line placements (Ch5's REDA
    DESTINATIONS, not its .xPosition staging tiles), the nine player start tiles, the three
    east-edge reinforcement pairs, the villages/armory/vendor/arena, and Joshua's own tile
    for Sahnar. The HOST SLOT supplies storage and nothing else; the two numbering offsets
    that make "ch05 on slot 6 filling Ch6Events" read like a bug are stated once, in the
    CH05_* constant block, and nowhere else.

    Rosters live in OUR OWN symbols (declare_unit_table -> MS_Ch05*), not in whichever
    vanilla table the stripped cutscenes left unreferenced. Slot 6 frees three and ch05 needs
    seven, so squatting would have meant borrowing Ch6's world-map ENCOUNTER rosters -- and
    the name would have lied either way.

    DEFERRED to follow-up passes (all authored, none blocking a load-test): the four
    reliquary village visits (their `visit_text` is still owed, #25), Basil's Talk recruit of
    Sahnar (the red-convertible flow already exists -- recruit_initial_faction), the opening/
    ending cutscenes (dialogue LOCKED in PR #196), the arena tutorial, and the title-card art.
    ch05's ending parks on the dev placeholder until ch06 hosts, exactly as ch04's did.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH05_CHAPTER_YAML)
    # A retile inherits vanilla's gift PLACEMENT, not just its terrain. Runs before anything is
    # written: the failure it catches is invisible to the parity read (same items, same total,
    # different tiles), so it has to be a gate rather than a review note.
    assert_village_gifts_match_vanilla(chap, CH05_ITEM_IDS)
    assert_village_tiles_visitable(chap, maps_dir, CH05_LAYOUT[1])

    # 1. Map: register the port-or-town-winter tileset (ch05 is its first user, so it
    #    self-registers -- the Cave/inject_ch03 idiom) and the painted layout, then point
    #    slot 6 at them and borrow slot 7's clean defeat_boss goal banner.
    _register_tileset(campaign, CH05_TILESET, TILESET_STEMS[CH05_TILESET],
                      'Manchego Stars port-or-town-winter tileset (#25)')
    indices = _register_chapter_map(maps_dir, CH05_LAYOUT,
                                    'Manchego Stars ch05 elven tomb layout (#25)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH05_HOST_INDEX, CH05_GOAL_DONOR, 'defeat_boss',
        'ERROR: slot %d goal is not the vanilla defeat_boss template (ch05 DefeatBoss donor)'
        % CH05_GOAL_DONOR, indices, chap['chapter_number'], CH05_EVENT_GROUP,
        (CH05_GOAL_WINDOW_MSG, CH05_GOAL_STATUS_MSG))

    # 2. Rosters. The cap template is NEVER LOADed -- PREP reads its entry count (the cap)
    #    and the YAML's deploy_slots tiles, then redeploys the player's picks (cf. ch03/ch04).
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    for uid, _slot, ce, _dce, _level in cast:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch05 field roster %s)' % (ce, uid))
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    cap_rows = _deploy_cap_entries(chap, cast, leader, 'ch05')
    declare_unit_table(CH05_ALLY_TABLE, cap_rows,
                       'ch05 PREP deploy-cap template (never LOADed; the CAP is the parity)')
    # --ch05-boot only: the field roster armed from CLASS_LOADOUT on the deploy tiles, so PREP
    # has a party to pick from a COLD New Game. The real chain omits it -- the party persists.
    slots = chap['deployment']['deploy_slots']
    seed_rows = [_ally_unit_entry(leader, slot, dce, level, x, y,
                                  ', '.join(CLASS_LOADOUT[ce]),
                                  ' /* %s -- ch05 boot party seed (armed; PREP re-picks) */' % uid)
                 for (uid, slot, ce, dce, level), (x, y) in zip(cast, slots)]
    declare_unit_table(CH05_BOOT_SEED_TABLE, seed_rows,
                       'ch05 --ch05-boot armed party seed (cold-start PREP fodder)')

    line_rows = ch05_enemy_rows(chap)
    declare_unit_table(CH05_LINE_TABLE, line_rows,
                       'ch05 turn-1 line: the risen tomb-guard, on vanilla Ch5 fighting tiles')
    wave_counts = {}
    for turn in sorted(CH05_WAVE_TABLES):
        rows = ch05_enemy_rows(chap, arrives_turn=turn, exclude=('sahnar',))
        if not rows:
            sys.exit('ERROR: ch05 declares no enemies arriving on turn %d, but a wave table '
                     'and TurnEventPlayer are wired for it' % turn)
        wave_counts[turn] = len(rows)
        declare_unit_table(CH05_WAVE_TABLES[turn], rows,
                           'ch05 eruption wave, turn %d (vanilla Ch5 raider spawns)' % turn)
    # Sahnar rides her own table so the wake beat (and Basil's Talk) can address her alone --
    # a shared pid is unaddressable, which is exactly what #203 cost ch04's wolf pack.
    sahnar_rows = ch05_enemy_rows(chap, arrives_turn=2, exclude=frozenset(
        e['id'] for e in chap['enemy_units'] if e['id'] != 'sahnar'))
    # Sahnar rises on her OWN CHARACTER slot (#251 gave her one -- Marisa), not a raw pid: the
    # Talk has to address HER and not the nearest identical myrmidon, and a shared pid is
    # unaddressable, which is precisely what #203 cost ch04's wolf pack. She rides the ENEMY
    # table, so the row is red by construction -- and that is exactly why her YAML's
    # `recruit.initial_faction: red` is checked rather than trusted: the field is what the
    # SHARED recruit flow reads to tell a red parley from a green bystander, so if it ever
    # disagreed with where she is actually placed, the flow would be reasoning about a unit
    # that is not on the map in that colour.
    sahnar = next(r for r in on_map_talk_recruits(campaign, chap['chapter_number'])
                  if r[0] == 'sahnar')
    sahnar_char = char_symbol(sahnar[1])
    if recruit_initial_faction(load_unit(campaign, 'sahnar')) != 'RED':
        sys.exit('ERROR: ch05 places Sahnar on the enemy table (RED), but her YAML '
                 'recruit.initial_faction does not say red')
    # Reading an UNWRITTEN vanilla id as placeholder prose is the reliquary pattern and is fine;
    # reading one ANOTHER hosted chapter writes shows that chapter's scene instead. Both look
    # identical here -- an int in a constant -- so the difference has to be a gate. Caught the
    # Basil join beat pointed at 0x9C2, which is ch04's own no-parley ending.
    assert_message_id_unclaimed(CH05_SAHNAR_TALK_MSG, 'ch05', "Basil's Talk recruit of Sahnar")
    sahnar_rows = [row.replace(CH05_GENERIC_PID, sahnar_char, 1) for row in sahnar_rows]
    declare_unit_table(CH05_SAHNAR_TABLE, sahnar_rows,
                       'ch05 Sahnar: rises HOSTILE at the eruption; Basil Talks her over (#25)')

    # Basil: GREEN at the pocket mouth, the Colm/Trex placement idiom -- her own table so the
    # PREP cap template stays the pure blue roster. Unlike Trex she is not joined by a CHAR
    # talk; the opening's own beat CUSAs her (see CH05_BASIL_GREEN_POS). She is a classed cast
    # member, so her slot/class come from the roster rather than being named here.
    basil = next(r for r in on_map_talk_recruits(campaign, chap['chapter_number'])
                 if r[0] == 'basil')
    basil_char = char_symbol(basil[1])
    basil_faction = recruit_initial_faction(load_unit(campaign, 'basil'))   # GREEN (the default)
    assert_green_recruit_placement(
        chap, maps_dir, CH05_LAYOUT[1], CH05_BASIL_GREEN_POS,
        CH05_BASIL_MOV_TABLE, 'Basil (ch05 green recruit)',
        must_reach=tuple(next(e for e in chap['enemy_units']
                              if e['id'] == 'sahnar')['positions'][0]))
    bx, by = CH05_BASIL_GREEN_POS
    declare_unit_table(CH05_BASIL_TABLE, [_ally_unit_entry(
        leader, basil[1], basil[3], basil[4], bx, by, ', '.join(CLASS_LOADOUT[basil[2]]),
        ' /* basil -- green until the opening join beat CUSAs her blue (#25) */',
        allegiance=basil_faction)],
        'ch05 Basil: %s at the pocket mouth; the opening join makes her the escort'
        % basil_faction)

    # 3. Strip the host slot's event lists and wire ours. The list SYMBOLS are the only
    #    vanilla names left in this function, and they come from CH05_EVENT_LISTS.
    with open(CH05_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    turn_rows = ''.join(
        '    TurnEventPlayer(0, %s, %d) /* eruption wave: %d */\n'
        % (CH05_WAVE_SCRIPTS[turn], turn, wave_counts[turn])
        for turn in sorted(CH05_WAVE_TABLES))
    info = _replace_brace_block(info, CH05_EVENT_LISTS['turn'] + '[] =',
                                '{\n' + turn_rows + '    END_MAIN\n}', CH05_EVENTINFO_H)
    # Misc = the win/lose machinery. DefeatBoss is an AFEV on EVFLAG_DEFEAT_BOSS, which
    # Ravisin's FLAGGED defeat quote sets on her death (step 5) -- CA_BOSS alone fires nothing.
    info = _replace_brace_block(
        info, CH05_EVENT_LISTS['misc'] + '[] =',
        '{\n    DefeatBoss(%s)\n    CauseGameOverIfLordDies\n    END_MAIN\n}'
        % CH05_ENDING_SCRIPT, CH05_EVENTINFO_H)
    # Location = the four reliquary visits + the elven store. The shops are wired for good (a
    # shop needs no script and no text); the visits own their rewards, and each carries its
    # CH05_VILLAGE_FLAGS event id -- the race (#25).
    info = _replace_brace_block(
        info, CH05_EVENT_LISTS['location'] + '[] =',
        ch05_location_events(chap), CH05_EVENTINFO_H)
    # The race's two tile states: a reliquary DESECRATED by a raider, and one closed behind the
    # party. Must run AFTER _retarget_host_chapter zeroed changeLayerId (as ch04's does).
    _inject_tile_changes('MS_Ch05MapChanges', ch05_map_changes(chap, maps_dir), CH05_HOST_INDEX)
    # Character = the Basil->Sahnar Talk, and nothing else -- structurally identical to vanilla
    # Ch5's single CHAR(NATASHA, JOSHUA). Recruiter set is Sahnar's own `parley.by` (Basil), the
    # gated flavour of the shared flow; ch03's Trex passes the whole roster instead. No
    # pre_script: unlike ch04's pack parley there is no group to bring over with her.
    sahnar_char_events, sahnar_talk_script = talk_recruit_wiring(
        parley_recruiters(next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')),
        sahnar_char, CH05_SAHNAR_TALK_FLAG, CH05_SAHNAR_TALK_SCRIPT, CH05_SAHNAR_TALK_MSG)
    info = _replace_brace_block(info, CH05_EVENT_LISTS['character'] + '[] =',
                                sahnar_char_events, CH05_EVENTINFO_H)
    for key in ('select_unit', 'select_dest', 'unit_move', 'tutorial'):
        info = _replace_brace_block(info, CH05_EVENT_LISTS[key] + '[] =',
                                    '{\n    END_MAIN\n}', CH05_EVENTINFO_H)
    # Point the group at OUR roster table. Declaring it is not enough -- the engine reads the
    # roster through the ChapterEventGroup, and until this line ch05 ran vanilla Ch6's ally
    # table: the party deployed on another map's coordinates, four of them inside walls, with
    # PREP running and the load-test PASSing. See point_event_group_at.
    for field in ('playerUnitsInNormal', 'playerUnitsInHard'):
        info = point_event_group_at(info, CH05_EVENT_GROUP, field, CH05_ALLY_TABLE)
    with open(CH05_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)
    assert_event_group_roster(CH05_EVENTINFO_H, CH05_EVENT_GROUP, CH05_ALLY_TABLE)

    # 4. Beginning scene + the wave scripts. LOMA rebuilds the battle map fresh, the line
    #    LOADs, then CALL Preparations (which reads the never-LOADed cap template).
    with open(CH05_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    seed_load = ('    LOAD1(0x1, %s) /* --ch05-boot: found an armed party */\n'
                 '    ENUN\n' % CH05_BOOT_SEED_TABLE) if boot else ''
    beginning = ('{\n'
                 '    MUSC(SONG_TENSION)\n'
                 '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
                 '    LOMA(0x%X) /* RestartBattleMap -- build the ch05 map fresh */\n'
                 % CH05_HOST_INDEX
                 + '    LOAD1(0x1, %s) /* the 16 risen tomb-guard */\n    ENUN\n'
                 % CH05_LINE_TABLE
                 + '    LOAD1(0x1, %s) /* Basil, GREEN at the pocket mouth */\n    ENUN\n'
                 % CH05_BASIL_TABLE
                 + seed_load
                 # NO FADU: the shared prep prologue fades to black itself before drawing
                 # Preparations, so revealing the freshly-LOMA'd map here only flashes it.
                 + '    CALL(%s) /* preparations: pick %d; lord force-deployed */\n'
                 % (CH05_PREP_SCRIPT, chap['deployment']['deploy_limit'])
                 # The join, AFTER Preparations and deliberately so. Basil is GREEN across the
                 # prep screen (prep only ever touches PLAYER units, so a green body is invisible
                 # to Pick Units and costs no slot), and becomes the party's tenth unit the moment
                 # the CUSA lands -- on top of the nine the player chose, which is what the
                 # chapter is priced for. CUSA before the CALL would hand PREP a blue unit it
                 # never listed.
                 # No TEXTSHOW: see CH05_BASIL_JOIN_MSG for why the beat is silent until the
                 # dialogue pass. Keeping it silent also keeps this script in vanilla's safe
                 # shape -- a script that continues with VISIBLE content after the prep prologue
                 # needs its own FADU(16) first (the prologue fades to black and leaves it
                 # there); the ones that ENDA straight out, as this does, do not.
                 + '    CUSA(%s) /* green -> blue: Basil is the escort now */\n'
                 '    ENUT(8)\n    EVBIT_T(7)\n    ENDA\n}'
                 % basil_char)
    script = _replace_brace_block(script, CH05_BEGINNING_SCRIPT + '[] =', beginning,
                                  CH05_EVENTSCRIPT_H)
    for turn in sorted(CH05_WAVE_TABLES):
        script = _replace_brace_block(
            script, CH05_WAVE_SCRIPTS[turn] + '[] =',
            ch05_wave_script(
                turn, CH05_WAVE_TABLES[turn], CH05_SAHNAR_TABLE if turn == 2 else None),
            CH05_EVENTSCRIPT_H)
    # The ending: the save-all-four payout, then the win. ch06 is not hosted yet, so the win
    # lands on the dev placeholder exactly as ch03's did until ch04 hosted (chain_ch04_to_ch05
    # advances the real path below).
    script = _replace_brace_block(script, CH05_ENDING_SCRIPT + '[] =',
                                  ch05_ending_script(chap), CH05_EVENTSCRIPT_H)
    with open(CH05_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 4b. The four reliquary visits, one script each so a site can get its own line later without
    #     disturbing the others. Vanilla's own village shape (village_script, shared with ch04):
    #     one text box over the interior BG, then the gift into the visitor's hands.
    #
    #     AFTER the bulk write, and that ordering is load-bearing: declare_event_script APPENDS to
    #     this file, while the block-replacement above rewrites it wholesale from a copy read
    #     earlier. Declaring first silently discards every appended script -- the Location list
    #     still names them, the externs still exist, and the build dies at link time pointing at
    #     the reference rather than the loss. assert_event_scripts_defined catches the reorder.
    for village in chap.get('villages', []):
        symbol, msg, _fid = CH05_VILLAGE_SLOTS[village['id']]
        declare_event_script(
            CH05_EVENTSCRIPT_H, symbol,
            village_script(msg, village_reward_item(village, CH05_ITEM_IDS), CH05_VISIT_BG),
            'ch05 %s -- the resident\'s line (0x%X) then the gift' % (village['id'], msg))
    # 4c. The Basil->Sahnar Talk script the Character list points at. Same append-AFTER-the-bulk-
    #     write rule as the visits above -- declaring it earlier would have the block rewrite
    #     discard it, and the build would die at link time pointing at the CHAR entry rather
    #     than at the loss.
    declare_event_script(
        CH05_EVENTSCRIPT_H, CH05_SAHNAR_TALK_SCRIPT, sahnar_talk_script,
        'ch05 Basil Talks Sahnar down -- CUSA red->blue; prose is vanilla 0x%X until the '
        'dialogue pass (#25)' % CH05_SAHNAR_TALK_MSG)
    assert_event_scripts_defined(
        CH05_EVENTSCRIPT_H, [slot[0] for slot in CH05_VILLAGE_SLOTS.values()]
        + [CH05_SAHNAR_TALK_SCRIPT])

    # 5. Texts + the flagged defeat quote that IS the win trigger.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + (boss.get('fe_name') or boss['name'])))
    set_message_body(lines, host['goal']['windowTextId'], goal_window_body('Defeat boss'))
    set_message_body(lines, CH05_ERUPTION_MSG, ch05_eruption_message(chap))
    # The four reliquary visits (#25). Each site's speaker is one of the tomb's risen dead, over
    # BG_HOUSE -- a full-screen backdrop, so these wrap at 42 like the other BG scenes and NOT at
    # the on-map bubble's 29. One `visit_text` entry per BOX, ch04's lesson: the authored A-press
    # breaks are the pacing (27 boxes against vanilla Ch5's own 26), and a flowed scalar would
    # reflow them to wherever 42 columns happen to land.
    for village in chap['villages']:
        _symbol, msg, fid = CH05_VILLAGE_SLOTS[village['id']]
        set_message_body(lines, msg, _script_to_message(
            [{'resident': box} for box in village_boxes(village)],
            {'resident': ('[OpenMidLeft]', fid)}, width=42))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    _write_chapter_title_card(host, 'Ch.5: ' + chap['title'])
    # .msg = 0 -> silent, like ch03's grell: Ravisin's authored death quote still needs its own
    # allocated id from ch05's host block. Her portrait is live now (#259); message ownership is
    # the remaining seam. The engine sets the flag either way -- DisplayDefeatTalkForPid only
    # SHOWS a quote if msg != 0, but SetPidDefeatedFlag runs regardless (eventinfo.c:595), and
    # the flag is what fires DefeatBoss.
    _prepend_defeat_quote(flag_defeat_quote(
        CH05_BOSS_PID, chapter_label_constant(CH05_HOST_INDEX), 'EVFLAG_DEFEAT_BOSS',
        'Ravisin (ch05 boss): silent defeat -> DefeatBoss WIN flag'))

    if verbose:
        print('  ch05 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; defeat_boss '
              'goal + DefeatBoss(Ravisin) WIN wired, PREP deploy cap %d%s + %d line + %s reinf '
              '+ Sahnar'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH05_HOST_INDEX, len(cap_rows),
                 ' (boot-seeded party)' if boot else '', len(line_rows),
                 '/'.join('t%d:%d' % (t, wave_counts[t]) for t in sorted(wave_counts))))


def chain_ch04_to_ch05():
    """Advance ch04's authored ending from the dev landing to the now-hosted ch05."""
    with open(CH5_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    landing = dev_placeholder_scene()
    if script.count(landing) != 1:
        sys.exit('ERROR: expected exactly one ch04 dev-placeholder landing before ch05 chain')
    script = script.replace(
        landing,
        '    MNC2(0x%X) /* -> ch05 "The Elven Tomb", hosted on slot %d */\n'
        % (CH05_HOST_INDEX, CH05_HOST_INDEX), 1)
    with open(CH5_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)


def chain_ch03_to_ch04():
    """Advance ch03's authored ending from the dev landing to the now-hosted ch04."""
    with open(CH4_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    landing = dev_placeholder_scene()
    if script.count(landing) != 1:
        sys.exit('ERROR: expected exactly one ch03 dev-placeholder landing before ch04 chain')
    script = script.replace(
        landing,
        '    MNC2(0x%X) /* -> ch04 "The White Moose", hosted on slot %d */\n'
        % (CH04_HOST_INDEX, CH04_HOST_INDEX), 1)
    with open(CH4_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)


def inject_northlook_bitey(verbose=True):
    """Mount 'Ol Bitey -- the Northlook's stuffed-fish trophy -- over the hearth (#21
    Beat 1 set dressing; Scramsax name-drops him in beat A). A custom edit to the vanilla
    bg_Fireplace convo background: restore the vanilla PNG first (idempotent across
    builds), paint a small cold-water fish using ONLY existing palette colours (so each
    8x8 tile stays within its 4bpp 16-colour bank), and drop the converted intermediates
    so `make` re-derives them. Centered on the hearth (fire centre x=135); the cool
    blue-purple tones read as a frozen-lake trophy and survive the tile conversion."""
    from PIL import ImageDraw
    bg = os.path.join(DECOMP, 'graphics', 'bg', 'bg_Fireplace.png')
    subprocess.run(['git', '-C', DECOMP, 'checkout', '--', 'graphics/bg/bg_Fireplace.png'],
                   check=True)
    im = Image.open(bg)
    pal = im.getpalette()
    # FE8 convo backgrounds are 4bpp: each 8x8 tile may only reference ONE 16-colour
    # sub-palette. The mantle tiles where Bitey hangs all use sub-palette BLOCK 5
    # (indices 80..95, the warm-stone tones) -- so the fish MUST be painted with block-5
    # indices, or the tile conversion can't fit its colours and garbles it to a black
    # blob (the old cool-blue fish drew from another block -> the in-game blob Nicolas
    # flagged). So a dark *smoked-fish* trophy in stone tones, reading against the light
    # tan wall by VALUE + a crisp black outline. Stamp explicit indices (not an RGB
    # lookup, which could resolve to the same colour in the wrong block).
    OUTL, BODY, BELLY, FIN, EYE = 80, 89, 82, 84, 92  # block-5 indices (see palette)
    cmap = {}
    def c(idx):
        rgb = tuple(pal[idx * 3:idx * 3 + 3])
        cmap[rgb] = idx
        return rgb + (255,)
    ov = Image.new('RGBA', (34, 15), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse([5, 3, 26, 11], fill=c(BODY), outline=c(OUTL))     # body
    d.arc([6, 6, 25, 12], 20, 160, fill=c(BELLY))               # belly sheen
    d.polygon([(12, 3), (20, 3), (16, 0)], fill=c(FIN))         # dorsal fin
    d.polygon([(25, 7), (33, 1), (30, 7), (33, 13)], fill=c(FIN), outline=c(OUTL))  # forked tail
    d.polygon([(12, 8), (16, 8), (12, 13)], fill=c(FIN))        # pectoral fin
    d.line([(5, 7), (1, 7)], fill=c(OUTL))                      # open mouth
    d.ellipse([7, 5, 10, 8], fill=c(EYE), outline=c(OUTL))      # eye socket (light, reads)
    d.point((8, 6), fill=c(OUTL))                               # pupil
    op, ovp = im.load(), ov.load()
    ox, oy = 118, 89                                             # centered over the hearth
    for y in range(15):
        for x in range(34):
            r, g, b, a = ovp[x, y]
            if a > 0:
                op[ox + x, oy + y] = cmap[(r, g, b)]
    im.save(bg)
    for ext in ('.feimg2.bin', '.feimg2.bin.lz', '.fetsa2.bin', '.gbapal'):
        stale = bg[:-4] + ext
        if os.path.exists(stale):
            os.remove(stale)
    if verbose:
        print("  'Ol Bitey mounted over the Northlook hearth (bg_Fireplace, #21)")


def inject_pc_death_quotes(campaign, verbose=True):
    """Universal per-PC death quotes (#6): when a deployable cast member falls, FE8's
    gDefeatTalkList machinery (DisplayDefeatTalkForPid, eventinfo.c) shows their dying
    line with their bust -- exactly the vanilla player-death-quote path (cf. Natasha
    MSG_9C6, Forde MSG_9DC). Entries go at the HEAD of the list (GetDefeatTalkEntry
    returns the first pid match) with route=ANY, chapter=0xFF and no flag, so they fire
    in EVERY chapter. Each PC rides its PORTRAIT_MAP slot, so pid + face = CHARACTER_<slot>
    / [FID_<slot>]. Quote text lives in the unit YAML (`death_quote`); bodies render via
    _script_to_message with the bust on the left podium, like the boss death quotes."""
    cast = classed_cast(campaign)
    # 1. Text bodies (each quote in a map talk box with the faller's bust, left podium).
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    rows = []
    for unit_id, slot, _, _ in cast:
        if unit_id not in PC_DEATH_QUOTE_MSGS:
            sys.exit('ERROR: no death-quote msg id allocated for cast member %r' % unit_id)
        unit = load_unit(campaign, unit_id)
        quote = unit.get('death_quote')
        if not quote:
            sys.exit('ERROR: %s YAML has no death_quote (#6 requires one per cast member)'
                     % unit_id)
        msg = PC_DEATH_QUOTE_MSGS[unit_id]
        set_message_body(lines, msg, _script_to_message(
            [{unit_id: quote}], {unit_id: ('[OpenMidLeft]', _fid_tag(slot))}))
        rows.append(
            '    {\n'
            '        .pid     = CHARACTER_%s, /* %s death quote (#6, any chapter) */\n'
            '        .route   = CHAPTER_MODE_ANY,\n'
            '        .chapter = 0xFF, /* fires in every chapter */\n'
            '        .msg     = 0x%04X,\n'
            '    },' % (slot.upper(), unit_id, msg))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    # 2. Prepend the entries at the head of gDefeatTalkList (same idiom as the boss
    #    quotes; distinct pids, so ordering vs. those is immaterial).
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n'
    if bq.count(head) != 1:
        sys.exit('ERROR: gDefeatTalkList head not in expected form in %s'
                 % BATTLEQUOTES_C)
    bq = bq.replace(head, head + '\n'.join(rows) + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)
    if verbose:
        print('  death quotes: %d cast members (chapter=any)' % len(rows))


# --- Battle ground platforms (#65): vendored snow/ice grounds + terrain remap -------
# FE8's battle platform (the ground combatants stand on) is terrain-driven
# (gBanimFloorfx -> battle_terrain_table[idx]); vanilla has no snow ground (the pale
# siroyuka1 is stone). We vendor F2E platforms from the FE-Repo {Cynon} pack into NEW
# battle_terrain_table slots, then remap the terrain->ground tables so our snow chapters
# resolve snow grounds per tile. Sources: campaigns/<c>/platforms/<stem>.png (indexed P,
# 256x32 -- the vanilla platform format). Decided: decisions.md (Art & Audio, 2026-06-23).
BANIM_TERRAIN_GFX = os.path.join(DECOMP, 'graphics', 'banim', 'terrain')
BANIM_TERRAIN_DATA_C = os.path.join(DECOMP, 'src', 'banim_terrain_data.c')
BANIM_TERRAIN_INCBIN_S = os.path.join(DECOMP, 'data', 'data_banim_terrain.s')
BANIM_POINTER_H_TERR = os.path.join(DECOMP, 'include', 'banim_pointer.h')
DATA_TERRAINS_C = os.path.join(DECOMP, 'src', 'data_terrains.c')
BANIM_BATTLEPARSE_C = os.path.join(DECOMP, 'src', 'banim-battleparse.c')
VARIABLES_H = os.path.join(DECOMP, 'include', 'variables.h')
CHAPTER_SETTINGS_JSON_PLAT = os.path.join(DECOMP, 'src', 'data', 'chapter_settings.json')

# (campaign png stem, decomp symbol stem, twilight tint). Grounds get table indices in
# append order from PLATFORM_BASE_INDEX. Offsets: 0=Snowdrift, 1=rough(SnowUneven), 2=Ice.
BATTLE_PLATFORMS = [
    ('snowdrift',         'snowdrift', 0.80),  # open windswept snow, cooled for twilight
    ('snow-uneven-light', 'snowrough', 1.00),  # rough snowy ground over rock
    ('ice-flat',          'snowice',   1.00),  # frozen lake/river
]
PLATFORM_BASE_INDEX = 115  # battle_terrain_table currently ends at 114
_PLAT_ICE = {'RIVER', 'SEA', 'LAKE', 'WATER', 'GLACIER', 'SNAG', 'DEEPS', 'SHIP_FLAT',
             'SHIP_WRECK'}
_PLAT_ROUGH = {'MOUNTAIN', 'PEAK', 'CLIFF', 'VALLEY', 'RUINS_REGULAR', 'RUINS_VILLAGE',
               'RUBBLE', 'PILLAR', 'WALL_REGULAR', 'WALL_DAMAGED', 'FENCE_REGULAR',
               'FENCE_32', 'FORT', 'GATE_CASTLE', 'GATE_REGULAR', 'SKY', 'BARREL', 'BONE',
               'DARK', 'GUNNELS', 'BRACE', 'MAST', 'BALLISTA_REGULAR', 'BALLISTA_LONG',
               'BALLISTA_KILLER'}


def _terrain_snow_ground(terrain, base, rough_open):
    """Ground index for TERRAIN_<terrain> on a snow map. rough_open=True (the Ch1 'rough'
    tileset) sends open/flat ground to the rough platform instead of the drift."""
    if terrain in _PLAT_ICE:
        return base + 2
    if terrain in _PLAT_ROUGH:
        return base + 1
    return base + (1 if rough_open else 0)


def inject_battle_platforms(campaign, verbose=True):
    """Vendor the snow/ice battle platforms + remap snow chapters' terrain->ground (#65).

    ADDING A PLATFORM (the repeatable how):
      1. Source from the FE-Repo `{Cynon} Battle Platforms` pack (F2E; back-up `{WAve}`). Pull one
         file without cloning the 2.3GB repo:
           gh api "repos/Klokinator/FE-Repo/contents/<URL-encoded path>" \\
             | python3 -c "import sys,json;[print(e['download_url']) for e in json.load(sys.stdin)]"
           curl -fsSL "<download_url>" -o campaigns/<c>/platforms/<stem>.png
         It MUST be indexed mode P, 256x32, <=16 colours, dense indices 0-15 (vanilla platform format).
         CREDIT the author in CREDITS.md. Pick the look book-grounded (Everlasting Rime = twilight ->
         Medium/Night palettes, not bright Light); record the per-chapter pick in decisions.md.
      2. Add it to BATTLE_PLATFORMS `(png stem, symbol stem, tint)` -- tint 0.80 cools a bright
         platform to twilight, 1.0 = as-is. It vendors (PNG->.4bpp.lz via the Makefile gbagfx rule +
         a generated .agbpal), appends an extern (banim_pointer.h), an .incbin (data_banim_terrain.s),
         and a battle_terrain_table row (banim_terrain_data.c; indices from PLATFORM_BASE_INDEX).

    PER-CHAPTER look: set a chapter's `battleTileSet` in chapter_settings.json to 0 (snow-OPEN ->
    Snowdrift, via BanimTerrainGroundDefault) or 0x15 (snow-ROUGH -> Uneven, via Tileset15). A third
    look (e.g. a frozen-lake chapter -> Ice) = add a BanimTerrainGround_Tileset16 + a `case 0x16` in
    banim-battleparse.c + point the chapter at it. Terrain category -> ground = _terrain_snow_ground
    (_PLAT_ICE / _PLAT_ROUGH / else drift). All patched decomp files are in PATCHED_DECOMP_FILES.
    Decisions/rationale: decisions.md (Art & Audio).
    """
    import json as _json
    import re as _re
    import struct as _struct
    from PIL import Image
    base = PLATFORM_BASE_INDEX
    plat_dir = os.path.join(REPO, 'campaigns', campaign, 'platforms')

    # 1. vendor each platform: png -> decomp (Makefile gbagfx makes .4bpp.lz) + agbpal
    externs, incbins, rows = [], [], []
    for n, (stem, sym, tint) in enumerate(BATTLE_PLATFORMS):
        im = Image.open(os.path.join(plat_dir, stem + '.png'))
        if im.mode != 'P':
            sys.exit('ERROR: platform %s must be indexed (mode P), got %s' % (stem, im.mode))
        tsym, psym = 'battle_terrain_ms_%s_tileset' % sym, 'battle_terrain_ms_%s_pal' % sym
        im.save(os.path.join(BANIM_TERRAIN_GFX, tsym + '.png'))
        pal = im.getpalette()
        blob = bytearray()
        for i in range(16):
            r, g, b = pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]
            if i != 0 and tint != 1.0:
                r, g, b = r * tint, g * tint, min(255, b * tint + 16)
            blob += _struct.pack('<H', (min(31, int(r) >> 3)) | (min(31, int(g) >> 3) << 5)
                                 | (min(31, int(b) >> 3) << 10))
        with open(os.path.join(BANIM_TERRAIN_GFX, psym + '.agbpal'), 'wb') as f:
            f.write(blob)
        externs += ['extern short %s[];' % psym, 'extern char %s[];' % tsym]
        incbins += ['\t.global %s' % tsym, '%s:' % tsym,
                    '\t.incbin "graphics/banim/terrain/%s.4bpp.lz"' % tsym, '\t.align 2, 0',
                    '\t.global %s' % psym, '%s:' % psym,
                    '\t.incbin "graphics/banim/terrain/%s.agbpal"' % psym, '\t.align 2, 0']
        rows.append('\t{"ms_%s", %s, %s, 0}, // %d  (FE-Repo {Cynon}, F2E)'
                    % (sym, tsym, psym, base + n))

    with open(BANIM_POINTER_H_TERR, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars battle platforms (#65) */\n' + '\n'.join(externs) + '\n')
    with open(BANIM_TERRAIN_INCBIN_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars battle platforms (#65) */\n' + '\n'.join(incbins) + '\n')

    # 2. append rows to battle_terrain_table[] (before its closing };). DRIFT GUARD: our grounds
    #    get indices from PLATFORM_BASE_INDEX, which assumes the (restored-vanilla) table holds
    #    exactly that many entries (0..base-1). If a submodule bump ever resizes the vanilla table,
    #    fail loudly here rather than silently mis-index the new grounds.
    with open(BANIM_TERRAIN_DATA_C, encoding='utf-8') as f:
        td = f.read()
    last = base - 1
    table_body = re.search(r'battle_terrain_table\[\]\s*=\s*\{(.*?)\n\};', td, re.S)
    vanilla_count = len(re.findall(r'^\s*\{".*?\}, //', table_body.group(1), re.M)) if table_body else -1
    if vanilla_count != base or ('// %d\n};' % last) not in td:
        sys.exit('ERROR: battle_terrain_table has %d entries, expected PLATFORM_BASE_INDEX=%d '
                 '(vanilla table size shifted -- update PLATFORM_BASE_INDEX)' % (vanilla_count, base))
    td = td.replace('// %d\n};' % last, '// %d\n' % last + '\n'.join(rows) + '\n};', 1)
    with open(BANIM_TERRAIN_DATA_C, 'w', encoding='utf-8') as f:
        f.write(td)

    # 3. terrain->ground remap. Default = snow-OPEN (prologue/sandbox, tileset 0);
    #    a new Tileset15 = snow-ROUGH (Ch1). Both reference the new grounds.
    with open(DATA_TERRAINS_C, encoding='utf-8') as f:
        dt = f.read()

    def _snow_body(default_body, rough_open):
        return _re.sub(
            r'\[TERRAIN_(\w+)\]\s*=\s*-?\d+,',
            lambda mm: '[TERRAIN_%s] = %d,'
            % (mm.group(1), _terrain_snow_ground(mm.group(1), base, rough_open)),
            default_body)

    m = _re.search(r'(BanimTerrainGroundDefault\[\] =\s*\{)(.*?)(\n\};)', dt, _re.S)
    open_body, rough_body = _snow_body(m.group(2), False), _snow_body(m.group(2), True)
    dt = dt[:m.start()] + m.group(1) + open_body + m.group(3) + dt[m.end():]
    rough_arr = 'CONST_DATA s8 BanimTerrainGround_Tileset15[] = {%s\n};\n\n' % rough_body
    dt = dt.replace('CONST_DATA s8 BanimTerrainGroundDefault[] = {',
                    rough_arr + 'CONST_DATA s8 BanimTerrainGroundDefault[] = {', 1)
    # Tileset16 = CAVE (ch03 Termalaine mine). Unlike snow, this uses EXISTING VANILLA platforms:
    # the mine floor -> siroyuka1 (the vanilla neutral STONE ground, battle_terrain_table[20], so
    # ground value 21) and rock walls/cliffs -> gake1 (table[4], value 5). No PNG/append/FE-Repo
    # pull needed. NOTE the vanilla convention is value == table_index + 1 (the consumer subtracts
    # 1); do NOT copy the snow base+offset idiom here.
    def _cave_body(default_body):
        return _re.sub(
            r'\[TERRAIN_(\w+)\]\s*=\s*-?\d+,',
            lambda mm: '[TERRAIN_%s] = %d,' % (mm.group(1), 5 if mm.group(1) in _PLAT_ROUGH else 21),
            default_body)
    cave_arr = 'CONST_DATA s8 BanimTerrainGround_Tileset16[] = {%s\n};\n\n' % _cave_body(m.group(2))
    dt = dt.replace('CONST_DATA s8 BanimTerrainGroundDefault[] = {',
                    cave_arr + 'CONST_DATA s8 BanimTerrainGroundDefault[] = {', 1)
    with open(DATA_TERRAINS_C, 'w', encoding='utf-8') as f:
        f.write(dt)

    # 4. extern (variables.h) + switch case (banim-battleparse.c) for Tileset15
    with open(VARIABLES_H, encoding='utf-8') as f:
        vh = f.read()
    vh = vh.replace('extern CONST_DATA s8 BanimTerrainGround_Tileset01[];',
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset15[];\n'
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset16[];\n'
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset01[];', 1)
    with open(VARIABLES_H, 'w', encoding='utf-8') as f:
        f.write(vh)
    with open(BANIM_BATTLEPARSE_C, encoding='utf-8') as f:
        bp = f.read()
    bp = bp.replace(
        '    case 0:\n    default:\n        return BanimTerrainGroundDefault[terrain];',
        '    case 0x15:\n        return BanimTerrainGround_Tileset15[terrain];\n\n'
        '    case 0x16:\n        return BanimTerrainGround_Tileset16[terrain];\n\n'
        '    case 0:\n    default:\n        return BanimTerrainGroundDefault[terrain];', 1)
    with open(BANIM_BATTLEPARSE_C, 'w', encoding='utf-8') as f:
        f.write(bp)

    # 5. point Ch1 (chapter idx 2) at the rough snow tileset (0x15); prologue (idx 1) keeps 0
    with open(CHAPTER_SETTINGS_JSON_PLAT, encoding='utf-8') as f:
        cs = _json.load(f)
    cs['chapters'][2]['battleTileSet'] = 0x15
    cs['chapters'][CH03_HOST_INDEX]['battleTileSet'] = 0x16  # ch03 cave -> siroyuka1 stone (Tileset16)
    with open(CHAPTER_SETTINGS_JSON_PLAT, 'w', encoding='utf-8') as f:
        _json.dump(cs, f, indent=2)

    if verbose:
        print('  %d platforms -> battle_terrain_table[%d..%d] (FE-Repo {Cynon}, F2E)'
              % (len(BATTLE_PLATFORMS), base, base + len(BATTLE_PLATFORMS) - 1))
        print('  terrain->ground: Default=snow-open (Snowdrift); Tileset15=snow-rough; Ch1->0x15')
        print('  Tileset16=CAVE (vanilla siroyuka1 stone / gake1 rock); ch03->0x16')


def normalise_decomp_shebangs(verbose=False):
    """Rewrite the decomp's Linux `#!/bin/python3` shebangs for macOS. Idempotent.

    fireemblem8u/scripts/ ships `#!/bin/python3`, which does not exist on macOS (and /bin is
    SIP-protected, so it cannot be created). setup-toolchain.sh rewrites them once -- but ANY
    `git checkout` inside the submodule reverts them: restore_vanilla_sources, a manual reset,
    a branch switch, `git checkout -- .` after a build. The NEXT build then dies on
    `bad interpreter: No such file or directory`, several minutes in, from a Makefile rule
    that looks unrelated (tsa_generator.py on a BG image).

    tools/build.sh already re-applies it, but the DOCUMENTED build command is plain `make`
    (CLAUDE.md), which bypassed the wrapper -- so the failure kept recurring. Every build
    runs this module via the Makefile, so doing it here closes the hole for good rather than
    relying on remembering the wrapper."""
    if platform.system() != 'Darwin':
        return 0
    fixed = 0
    for path in glob.glob(os.path.join(DECOMP, 'scripts', '**', '*.py'), recursive=True):
        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        if not text.startswith('#!/bin/python3'):
            continue
        with open(path, 'w', encoding='utf-8') as f:
            f.write('#!/usr/bin/env python3' + text[len('#!/bin/python3'):])
        fixed += 1
    if fixed and verbose:
        print('  normalised %d Linux #!/bin/python3 shebang(s) in fireemblem8u/scripts '
              '(reverted by the last submodule checkout)' % fixed)
    return fixed


def main():
    ap = argparse.ArgumentParser(description='Inject campaign content into the decomp build.')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--portraits-only', action='store_true',
                    help='only inject portrait assets (skip names + characters)')
    ap.add_argument('--montage', action='store_true',
                    help='wire the #43 opening montage (lore crawl) instead of the '
                         'dev boot cut; dev builds keep the straight-to-map boot')
    ap.add_argument('--test-chapter', action='store_true',
                    help='PLAYTEST build: New Game boots straight into a Ch1 sandbox '
                         'with the whole cast deployed + the (reskinned) foes, cutscenes '
                         'stripped -- skips the prologue grind for fast in-engine testing. '
                         'Mutually exclusive with the prologue (both host chapter slot 1).')
    ap.add_argument('--lord-boot', action='store_true',
                    help='DEBUG fast-boot (#46, implies --test-chapter): the Ch1 sandbox '
                         'opens straight into the lord-select prep screen on New Game, so '
                         'iterating on that screen is compile-time only -- no playthrough '
                         'grind (see decisions.md / the debug-fast-boot convention).')
    ap.add_argument('--ch03-boot', action='store_true',
                    help='PLAYTEST build (#23): New Game boots straight into the Ch3 '
                         '"Termalaine Mine" on slot 4 -- the party deployed at the left '
                         'entrance + the 10 vanilla-Ch3-parity foes, cutscenes stripped '
                         '(fast-boot map load-test; mutually exclusive with the prologue).')
    ap.add_argument('--ch04-boot', action='store_true',
                    help='PLAYTEST build (#24): New Game boots straight into the Ch4 '
                         '"White Moose" snowy forest on slot 5 with an armed party, fog, '
                         'and the approved 16 + 4 + 3 vanilla-monster force.')
    ap.add_argument('--ch05-boot', action='store_true',
                    help='PLAYTEST build (#25): New Game boots straight into the Ch5 '
                         '"Elven Tomb" on slot 6 with an armed party, the 16 risen '
                         'tomb-guard on vanilla Ch5\'s own fighting tiles, and the three '
                         'eruption waves.')
    args = ap.parse_args()
    # Snapshot the flags AS PASSED, before --lord-boot implies --test-chapter below:
    # the build stamp has to describe the `make` invocation, not the derived state.
    _requested_flags = {'TESTCH': args.test_chapter, 'LORDBOOT': args.lord_boot,
                        'MONTAGE': args.montage, 'CH03BOOT': args.ch03_boot,
                        'CH04BOOT': args.ch04_boot, 'CH05BOOT': args.ch05_boot}
    if args.lord_boot:
        args.test_chapter = True  # the fast-boot rides the sandbox
    # Each fast-boot repoints New Game at its own slot, so at most one may win. Named
    # explicitly rather than counted, so the error says which flags actually clash.
    _boots = [name for name, on in (('--ch03-boot', args.ch03_boot),
                                    ('--ch04-boot', args.ch04_boot),
                                    ('--ch05-boot', args.ch05_boot)) if on]
    if len(_boots) > 1:
        sys.exit('ERROR: %s are mutually exclusive -- each repoints New Game at its own '
                 'chapter slot' % ' and '.join(_boots))

    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
    # Before anything else: undo whatever the last submodule checkout did to the decomp's
    # Linux shebangs, or this build dies minutes later on `bad interpreter`.
    normalise_decomp_shebangs(verbose=True)
    # Snapshot the previous build's injection footprint BEFORE we touch anything, so
    # we can rewind mtimes for whatever comes out byte-identical (fast warm rebuilds).
    _mtime_snapshot = _snapshot_mtimes(_decomp_footprint())
    print('portraits:')
    inject_portraits(args.campaign)
    if not args.portraits_only:
        restore_vanilla_sources()  # clean base each build (idempotent; vanilla donor reads)
        print('engine hardening:')
        engine_hooks._patch_player_start_cursor_guard()
        print('  GetPlayerStartCursorPosition: fall back to first player unit if leader undeployed')
        engine_hooks._patch_terrain_name_guard()
        print('  GetTerrainName: bounds-guarded against OOB terrain ids (defensive)')
        engine_hooks._patch_battle_map_kind_fallback()
        print('  GetBattleMapKind: no-world-map fallback = STORY (slot 2+ chapters)')
        engine_hooks._patch_chapter_title_wm_fallback()
        print('  GetChapterTitleWM: no-world-map fallback = ROM chapTitleId (not a WM skirmish name)')
        engine_hooks._inject_lord_select_engine()
        print('  lord select (#42): GetPid + force-deploy/Seize/game-over keyed to the chosen lead')
        engine_hooks._inject_lord_floor_engine()  # after lord-select: anchors on its LordSelect_GetPid
        print('  lord floor (#45 3c): chosen lead\'s survivability top-up baked in once at ch start')
        engine_hooks._patch_banim_character_unique()
        print('  banim (#65): combat anim lookup -> GetBattleAnimationId_WithUnique (per-character _u25)')
        engine_hooks._patch_banim_palette_custom_guard()
        print('  banim (#65): GetBanimPalette -> custom (appended) banims keep own palette (RBG cyan fix)')
        engine_hooks._patch_banim_unique_pal_custom_guard()
        print('  banim (#206): the per-CHARACTER palette no longer overwrites a custom banim\'s own '
              '(Baxby wore Forde\'s green)')
        engine_hooks._patch_banim_spell_palette_tint()
        print('  banim (#165): character/weapon spell palettes support campaign-declared tints')
        engine_hooks._patch_banim_charge_flash()
        print('  banim (#183): casters pulse their signature colour on the wind-up charge beat')
        engine_hooks._patch_draw_icon_pal2()
        print('  item icons (#23): DrawIcon routes gMSPal2IconIds from BG bank 4 to custom bank 15')
        print('names:')
        inject_names(args.campaign)
        print('item names:')
        inject_item_names(args.campaign)
        print('item icons:')
        inject_item_icons(args.campaign)
        inject_item_icon_pal2(args.campaign)
        print('characters:')
        patch_character_data(args.campaign)
        patch_raw_pid_portraits(args.campaign)
        print('portrait geometry:')
        patch_portrait_geometry(args.campaign)
        print('map sprites:')
        # One SMS id pool for the whole build -- both sprite passes below spend from it (#227).
        sms_alloc_reset(args.campaign, verbose=True)
        inject_map_sprites(args.campaign)
        print('enemy class reskins (#21):')
        inject_enemy_class_reskins(args.campaign)  # after map sprites (SMS ids), before ch01
        sms_alloc_report()
        print('enemy class battle anims (#90):')
        inject_enemy_class_battle_anims(args.campaign)  # after reskins (binds the clone class)
        print('battle anims (#65):')
        inject_battle_anims(args.campaign)
        print('winter tileset:')
        inject_winter_tileset(args.campaign)
        print('battle platforms (#65):')
        inject_battle_platforms(args.campaign)
        print('crit flourish (#11):')
        inject_crit_flourish(args.campaign)
        print('title theme:')
        inject_title_theme(args.campaign)
        print('title screen:')
        inject_title_screen(args.campaign)
        print('event backgrounds (#22):')
        inject_backgrounds(args.campaign)  # vendored winter BGs -> new gConvoBackgroundData slots
        # Ownership gate (#198 review): fail the build BEFORE any injector writes text if two
        # hosted chapters claim one message id -- a double-claim is otherwise silent, since
        # verify_text checks runaway text, not who owns a slot.
        assert_message_ids_unique()
        print('chapter 1 (#21):')
        inject_ch01(args.campaign)  # MUST precede inject_prologue (vanilla goal read)
        inject_northlook_bitey()    # 'Ol Bitey over the tavern hearth (Beat 1 set dressing)
        print('chapter 2 (#22):')
        inject_ch02(args.campaign)  # hosts slot 3; ch01's ending MNC2(0x3) lands here
        inject_ch02_chwinga_faces(args.campaign)  # green chwinga bust + Mote/Rime/Glimmer names
        print('chapter 3 (#23):')
        inject_ch03(args.campaign, boot=args.ch03_boot)
        print('chapter 4 (#24):')
        inject_ch04(args.campaign, boot=args.ch04_boot)
        chain_ch03_to_ch04()
        print('chapter 5 (#25):')
        inject_ch05(args.campaign, boot=args.ch05_boot)
        inject_ch05_visit_faces(args.campaign)  # the four reliquary residents' skeleton busts
        chain_ch04_to_ch05()
        if args.ch05_boot:
            print('CH05 BOOT (playtest: New Game -> the Elven Tomb, party + foes deployed):')
            _configure_boot(CH05_HOST_INDEX)
        elif args.ch04_boot:
            print('CH04 BOOT (playtest: New Game -> White Moose forest, party + foes deployed):')
            _configure_boot(CH04_HOST_INDEX)
        elif args.ch03_boot:
            print('CH03 BOOT (playtest: New Game -> Termalaine Mine, party + foes deployed):')
            _configure_boot(CH03_HOST_INDEX)
        else:
            if args.test_chapter:
                print('TEST CHAPTER (playtest: New Game -> Ch1 sandbox, cast deployed):')
                inject_test_chapter(args.campaign, lord_boot=args.lord_boot)   # slot 1 sandbox, in place of the prologue
                _configure_boot(TEST_CHAPTER_INDEX)  # sandbox never montages
            else:
                print('prologue (New Game target):')
                inject_prologue(args.campaign, montage=args.montage)
                _configure_boot(PROLOGUE_HOST_INDEX, montage=args.montage)
        print('death quotes (#6):')
        inject_pc_death_quotes(args.campaign)
    rewound = _rewind_unchanged_mtimes(_mtime_snapshot)
    if rewound:
        print('idempotent injection: rewound %d unchanged file(s) -> make skips them'
              % rewound)
    _stamp_build_config(args.campaign, _requested_flags)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
