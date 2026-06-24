#!/usr/bin/env python3
"""build_campaign.py -- inject campaign content into the fireemblem8u decomp build.

Reads campaign data (YAML + authored busts) and writes decomp-native source/asset
files into the fireemblem8u submodule working tree, so a plain `make` compiles a
ROM carrying our content. The generated files are reproducible build artifacts --
restore vanilla with `git -C fireemblem8u checkout <path>`.

Engine/Content boundary (CLAUDE.md): the GENERATOR knows character/chapter names;
the C/asm it EMITS is just data. No campaign name is ever hardcoded in engine C.

--- Milestone A (current): PORTRAITS ---------------------------------------------
For each named cast member, run the bust through portrait_tool.generate (4 decomp
assets) and overwrite a vanilla portrait slot's source files in
graphics/portrait/. The decomp's generic gbagfx pattern rules rebuild the
.4bpp/.4bpp.fk/.4bpp.lz on the next `make`; data_portrait[] is untouched, so the
mapped vanilla character simply wears our face. Zero C changes, fully reversible.

Milestones B+ (characters, chapter, dialogue codegen) hang off the same CLI.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# portrait_tool lives next to us in tools/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_tool  # noqa: E402
import map_sprite_tool  # noqa: E402
import ref_to_battleframe  # noqa: E402  faked-battle-anim asset generator (#65)
import gen_chapter_title  # noqa: E402
import gen_subtitle_cards  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402
from inject.decomp import (  # noqa: E402  shared decomp paths + patch primitives
    REPO, DECOMP, _find_brace_block, _replace_brace_block,
    BATTLEQUOTES_C, BMUNIT_C, LORDSEL_FLAG_BASE,
    WEAPON_ITEM_ENUM, fe_item_enum)  # shared weapon<->ITEM map (used by inject_prologue)
from inject import engine_hooks  # noqa: E402  campaign-agnostic engine C-source hooks

PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')
CHARACTERS_C = os.path.join(DECOMP, 'src', 'data_characters.c')
CLASSES_C = os.path.join(DECOMP, 'src', 'data_classes.c')
CLASSES_H = os.path.join(DECOMP, 'include', 'constants', 'classes.h')
# Faked battle anims (#65): the decomp files the injection appends to / patches.
BANIM_DATA_C = os.path.join(DECOMP, 'src', 'banim_data.c')
BANIM_POINTER_H = os.path.join(DECOMP, 'include', 'banim_pointer.h')
BANIMCONF_C = os.path.join(DECOMP, 'src', 'data_banimconf.c')
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
# names + portraits + classes + stats together. These are the only two files it touches.
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
PROLOGUE_CHAPTER_INDEX = 0   # CHAPTER_L_PROLOGUE -- the vanilla slot we configure then clone
PROLOGUE_HOST_INDEX = 1      # CHAPTER_L_1 -- normal chapter slot we actually load (New Game
                             # redirects 0 -> 1). The prologue slot has special engine paths
                             # that break our stripped chapter; a normal slot does not.
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
CH01_HOST_INDEX = 2          # CHAPTER_L_2 -- the prologue ending's MNC2(0x2) target
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
# bakes into the chosen lead's saved stats exactly once. Permanent flags span 100..299
# (GetPermanentFlagBitsSize = 0x19 bytes), so 0xFA is in range and free.
LORDSEL_PROMPT_MSG = 0x957   # dead vanilla slot-2 scene text (cf. inject_ch01 step 6)
LORDSEL_CONFIRM_MSGS = (0x959, 0x95A, 0x95B, 0x95C, 0x95D, 0x95E, 0x95F,
                        0x962, 0x963, 0x964)  # same dead pool, one per candidate
# Beat 1 (#21) "The Northlook" scenic opening: a location card + one message per
# beat (A-E), all riding dead vanilla Ch1-tutorial slot-2 message ids (the prologue
# host strips Ch1's tutorial event lists, so these never display in our ROM).
CH01_BEAT1_CARD_MSG = 0x945
CH01_BEAT1_MSGS = (0x940, 0x941, 0x942, 0x943, 0x944)  # A,B,C,D,E (0x945 = card)
# ch01 ending "The Rolling Cheddar" (#21): a "Bryn Shander" location card + one message
# per beat (A-F), on the same dead vanilla Ch1-tutorial slot-2 pool as Beat 1 (the
# prologue host strips Ch1's event lists, so these ids never display in our ROM).
CH01_ENDING_CARD_MSG = 0x94C
# AB,C,D,E1,E2(narration),E2b(Marty/Baxby),F. 0x93D is a dead vanilla Ch1-tutorial
# slot-2 id (weapon-triangle blurb, stripped by the prologue host) reused for the
# faceless "Marty leans in..." narration that #58 split into its own opaque box.
CH01_ENDING_MSGS = (0x946, 0x947, 0x948, 0x949, 0x93D, 0x94A, 0x94B)
CH01_BODY_MSG = 0x956    # the dismembered sled-driver, found just past the road sign
CH01_TAUNT_MSG = 0x960   # Izobai's turn-1 boss taunt (both dead vanilla Ch1-tutorial slots)
# Per-PC death quotes (#6, dialogue pass 2026-06-17): one universal dying line per
# deployable cast member, shown with their bust when they fall in ANY chapter. Each
# rides a dead vanilla Ch1-tutorial slot-2 message id (the prologue host strips Ch1's
# tutorial event lists, so these never display in our ROM -> safe campaign-wide).
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
CH02_HOST_INDEX = 3          # CHAPTER_L_3 -- ch01's ending MNC2(0x3) target
CH02_LAYOUT = ('Ch02ColdWelcomeMap', 'ch02-cold-welcome')  # (asset label, maps/ stem)
CH02_CHAPTER_YAML = 'ch02-cold-welcome.yaml'
CH02_BOSS_SLOT = 'BAZBA'      # vanilla Ch3's boss slot -- Halvar mirror (custom bust #19 later)
CH02_MINIBOSS_SLOT = 'BONE'   # vanilla Ch2's named mid-tier, idle on slot 3 -- Grukk (bust later)
# Vellynne Harpell (recurring Brotherhood NPC) has no map unit in ch02; her CUTSCENE FACE
# rides FID_Ismaire -- a regal vanilla woman absent from our ch00-08 chapters, collision-free.
# Her custom bust (#19) is OPTIONAL: this is a flagged placeholder until that art lands.
CH02_VELLYNNE_SLOT = 'ISMAIRE'
CH02_FISHER_FID = '[FID_VillagerOldMan]'   # the brittle Targos fisher -- generic villager mug
CH02_OPENING_BG = 'BG_NORMAL_VILLAGE'      # Bryn Shander west gate (placeholder BG; polish later)
CH02_ENDING_BG = 'BG_NORMAL_VILLAGE'       # Targos square at nightfall (placeholder BG)
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
                 'slim-lance': 'ITEM_LANCE_SLIM',
                 'red-gem': 'ITEM_REDGEM', 'elixir': 'ITEM_ELIXIR', 'pure-water': 'ITEM_PUREWATER'}
CH02_GENERIC_PID = '0x8e'    # vanilla slot-3 generic-minion charIndex (autolevelled trash)
# The three GREEN chwinga (protect layer): each rides a distinct minor vanilla NPC slot so
# its survival is individually trackable via CHECK_ALIVE at the ending scene. Slots are
# collision-free (absent from our ch00-08); their map sprite + portrait + name-text
# (Mote/Rime/Glimmer) are the art checkpoint (#38/#39) -- placeholder vanilla faces meanwhile.
# (yaml_id, vanilla character slot, charm-gift item the survivor delivers)
CH02_CHWINGA = (
    ('chwinga-mote',    'DARA',   'red-gem'),
    ('chwinga-rime',    'KLIMT',  'elixir'),
    ('chwinga-glimmer', 'MANSEL', 'pure-water'),
)
# The chwinga wear Sclorbo's chwinga map sprite (he is one), recoloured by the green NPC
# faction palette -- identical green triplets (Nicolas 2026-06-24). Build-time derived from
# this cast sprite; see _inject_ch02_chwinga_sprites.
CH02_CHWINGA_SPRITE_SRC = 'sclorbo'
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
                        # enemy class reskins (#21): cloned goblin classes in gClassData
                        'src/data_classes.c',
                        # faked battle anims (#65): appended banim_data row + pointer
                        # externs + linker block; the Archer-CLONE class + its new AnimConf
                        # (data_classes.c already listed); the AnimConf's extern decl
                        'src/banim_data.c', 'include/banim_pointer.h',
                        'src/data_banimconf.c', 'include/ekrbattle.h',
                        'linker_script_banim.txt',
                        # battle ground platforms (#65): vendored snow/ice grounds appended to
                        # battle_terrain_table + the terrain->ground remap (snow chapters)
                        'src/banim_terrain_data.c', 'data/data_banim_terrain.s',
                        'src/data_terrains.c', 'src/banim-battleparse.c', 'include/variables.h',
                        # Goodberry (#21): vulnerary icon swapped by inject_item_icons
                        'graphics/item_icon/item_icon_vulnerary.png',
                        'data/const_data_unit_icon_wait.s', 'data/const_data_unit_icon_move.s',
                        'include/unit_icon_pointer.h',
                        'data/const_data_chapter_maps.s', 'data/data_8B363C.s',
                        'src/data/chapter_settings.json',
                        'src/events/prologue-eventudefs.h', 'src/events/prologue-eventinfo.h',
                        'src/events/prologue-eventscript.h', 'src/data_battlequotes.c',
                        # ch01 host slot (#21): Ch2 events + the shared udefs TU;
                        # slot 2's title card is regenerated by inject_ch01
                        'src/events/ch2-eventinfo.h', 'src/events/ch2-eventscript.h',
                        'src/events_udefs.c', 'graphics/chap_title/chap_title_2.png',
                        # host slot's title card (chapTitleId 1); regenerated by
                        # inject_prologue from the chapter YAML's title
                        'graphics/chap_title/chap_title_1.png',
                        # title banner palettes; repointed by inject_title_theme
                        'data/data_A01CC4.s', 'data/data_A21658.s',
                        # opening-montage lore crawl (#43): card slides + LUT timers
                        # + aurora mural incbins, regenerated by inject_opening_montage
                        # on MONTAGE=1 builds
                        'src/opsubtitle.c', 'data/data_opsubtitle.s',
                        # world-map tour (#43): drawn-map selector patched in by
                        # inject_world_tour on MONTAGE=1 builds
                        'src/worldmap_rm.c',
                        # battle-map-kind fallback patch (no world map -> STORY)
                        'src/worldmap_path.c',
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
    'Knight':         'CLASS_ARMOR_KNIGHT',
    'Pegasus Knight': 'CLASS_PEGASUS_KNIGHT',
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
# (portrait-only mapping; class/stat mapping comes in Milestone B.)
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
    # ch01 recruit Baxby the axe-beak (npcs/baxby.yaml) rides the vanilla Forde slot --
    # a Cavalier (matching Baxby's donor class) absent from our MVP chapters (ch00-08),
    # so dressing FID_Forde with baxby.png is collision-free. This wires his CUTSCENE
    # FACE (he speaks in the ch01 ending); his recruit UNIT + map sprite ride this same
    # Forde character slot when that wiring lands (see HANDOFF "Wire Baxby" b/c).
    'baxby':          'Forde',
}


def _bust_dir(campaign):
    return os.path.join(REPO, 'campaigns', campaign, 'portraits')


def dressed_guest_slots(campaign):
    """Portrait slots of guests whose bust PNG exists (and so get dressed)."""
    return [slot for unit, slot in GUEST_PORTRAIT_MAP.items()
            if os.path.isfile(os.path.join(_bust_dir(campaign), unit + '.png'))]


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
    (not one tile off, which doubles it). See PORTRAIT_GEOMETRY."""
    slots = sorted(set(PORTRAIT_MAP.values()) | set(dressed_guest_slots(campaign)))
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
    """
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
    when a message's printable-char count is ODD the 0x00 terminator can't stand alone,
    so the decoder runs past [X] into the next message (garbage + bleed-through). Pad
    with a [.] before [X] to flip parity even. No-op when already even."""
    visible = re.sub(r'\[[^\]]*\]', '', body).replace('\n', '')
    if len(visible) % 2 and body.endswith('[X]'):
        body = body[:-3] + '[.][X]'
    return body


def _script_to_message(script, staging, width=29, face_budget=4, preload=None):
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
    return '\n'.join(parts) + '[X]'


def _beat_is_narration(beat):
    """True if every entry in a scenic beat is faceless `narration` stage-business."""
    return bool(beat) and all('narration' in e for e in beat)


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


# --- Milestone B: character stats / class -----------------------------------------
# Write each cast unit's vanilla-class identity into its portrait slot's
# gCharacterData[] entry: defaultClass, affinity (Anima, cosmetic), baseLevel,
# personal base stats = (YAML fe_stats - class base), the class's weapon-type rank,
# and zeroed personal growths (so the unit grows at its pure class rate). When
# fe_stats match the class verbatim (the FE-strict default) the personal bases come
# out 0; any deliberate YAML divergence is still honored so displayed stats ==
# fe_stats. portraitId, attributes (gender), and pSupportData are left as the
# vanilla slot's -- gender/supports are a later YAML-driven pass.

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

    A unit with a faked battle anim (#65) rides a stat-identical *clone* class (`clone_into`)
    so ONLY its own unit shows the custom anim -- generic/enemy units of the donor class keep
    the vanilla anim. Everyone else deploys as their plain class. Stats/loadout still resolve
    against `class_enum_for` (the real vanilla class), so the clone is invisible to them."""
    ba = unit.get('battle_anim')
    if ba and ba.get('clone_into'):
        return ba['clone_into']
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
# Result: New Game -> Ch1 map with the 8 cast, no cutscene, no game over -- a pure
# look-test (no enemies, no objective; reset when done). Each cast unit rides its
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
    'CLASS_ARMOR_KNIGHT':   ['ITEM_LANCE_IRON', 'ITEM_VULNERARY'],
    'CLASS_PEGASUS_KNIGHT': ['ITEM_LANCE_SLIM', 'ITEM_LANCE_JAVELIN', 'ITEM_VULNERARY'],
}
# Centered, spread-out formation on the Ch1 map (a 4x2 grid, 2-tile gaps), clear of the
# houses (13,6)/(10,4) and seize (2,2). Pulled in from the old bottom-right cluster so the
# cast reads spaced out toward the middle for the look-test. Roster fills in order.
TEST_SPAWN_POSITIONS = [(5, 4), (7, 4), (9, 4), (11, 4),
                        (5, 6), (7, 6), (9, 6), (11, 6)]


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
    game's prologue (skirmishes use PLAY_FLAGs; later chapters nonzero). Only the test
    sandbox needs this; the real prologue IS chapter 0, so it doesn't redirect."""
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


def inject_test_chapter(campaign, verbose=True):
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
        print('  Ch1 stripped to sandbox; boot attract + Magvel intro cut; '
              'New Game boots into Ch1')


# --- Map (overworld) sprites (#38) ------------------------------------------------
# FE8 draws map sprites by class (GetUnitSMSId -> pClassData->SMSId). To give each
# cast member a distinct overworld sprite without touching stock classes or vanilla
# enemies, we add a custom SMS slot per cast member (ids CUSTOM_SMS_BASE+) and a
# per-CHARACTER override in GetUnitSMSId. Colours come from the one shared cast
# palette (unit_icon_pal_player.agbpal) -- map sprites can't carry their own.


def classed_cast(campaign):
    """Cast (PORTRAIT_MAP order) that carry an FE class, each paired with a stable
    custom SMS id (CUSTOM_SMS_BASE + position). Name-only units are skipped. Ids are
    position-based so a unit keeps the same id whether or not its sprite is authored."""
    out, i = [], 0
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        if class_enum_for(unit) is None:
            continue
        out.append((unit_id, slot, class_enum_for(unit), CUSTOM_SMS_BASE + i))
        i += 1
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
        'extern unsigned short gMapSpriteOverride[];\n\n'
        'int GetUnitSMSId(struct Unit* unit) {\n'
        '    if (!(unit->state & US_IN_BALLISTA)) {\n'
        '        /* Campaign per-character map-sprite override (build-injected; the\n'
        '         * table is empty in vanilla). Lets a cast member wear a custom\n'
        '         * overworld sprite its stock class -- and any enemy of that class\n'
        '         * -- does not. */\n'
        '        const unsigned short * mso = gMapSpriteOverride;\n'
        '        int charId = UNIT_CHAR_ID(unit);\n'
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
        'extern struct CharMuImg gMuImgOverride[];\n\n'
        'const void * GetMuImg(struct MuProc * proc)\n'
        '{\n'
        '    /* Campaign per-character MU (hover/walk) sprite override (build-injected;\n'
        '     * empty in vanilla). Reuses the class motion script -- graphics only. */\n'
        '    if (proc->unit) {\n'
        '        struct CharMuImg * it = gMuImgOverride;\n'
        '        int charId = UNIT_CHAR_ID(proc->unit);\n'
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
    Pads short palettes with black; errors if it carries more than 16 entries."""
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


def _inject_palette_bank_hook():
    """Patch bmudisp.c so the custom cast share a bespoke palette in the campaign-unused
    purple OBJ bank (0xB / OBJPAL_UNITSPRITE_PURPLE), leaving the shared player palette
    (blue bank) untouched -- so the not-yet-custom cast still render correctly:
      * GetUnitSpritePalette -- per-character override returning the purple bank before
        the faction switch. StartMu uses this too, so it covers idle + hover/walk; the
        grey "acted" tint is handled upstream in GetUnitDisplayedSpritePalette.
      * ApplyUnitSpritePalettes -- load gCastMapPalette into the purple bank (replacing
        the single-player Light-Rune load; Light Rune is an unused DUMMY item)."""
    with open(BMUDISP_C, encoding='utf-8') as f:
        text = f.read()

    gsp_orig = ('int GetUnitSpritePalette(const struct Unit * unit)\n'
                '{\n'
                '    switch (UNIT_FACTION(unit)) {\n')
    gsp_hooked = (
        'extern unsigned short gMapPaletteOverride[];\n\n'
        'int GetUnitSpritePalette(const struct Unit * unit)\n'
        '{\n'
        '    /* Campaign per-character map-palette override (build-injected; empty in\n'
        '     * vanilla). Custom cast wear a bespoke palette in the purple bank so the\n'
        '     * shared player (blue) palette stays untouched. */\n'
        '    const unsigned short * mp = gMapPaletteOverride;\n'
        '    int charId = UNIT_CHAR_ID(unit);\n'
        '    while (*mp != 0xFFFF) {\n'
        '        if (*mp == charId)\n'
        '            return OBJPAL_UNITSPRITE_PURPLE;\n'
        '        mp++;\n'
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

    # prep_unitselect.c: PrepUnit_InitSMS loads the unit-sprite palettes (incl. our cast
    # palette into the purple bank 0x0B) then immediately zeros bank 0x0B -- vanilla
    # cleanup that's harmless there (no purple-faction units in prep) but blanks our
    # custom cast map sprites to BLACK silhouettes on the Pick Units roster. Drop the
    # fill: ApplyUnitSpritePalettes already left bank 0x0B holding the correct cast palette.
    with open(PREP_UNITSELECT_C, encoding='utf-8') as f:
        prep = f.read()
    fill_orig = ('    ApplyUnitSpritePalettes();\n'
                 '    CpuFastFill(0, PAL_OBJ(0x0B), 0x20);\n')
    fill_hooked = ('    ApplyUnitSpritePalettes();\n'
                   '    /* Manchego Stars: vanilla zeros the purple OBJ bank (0x0B) here --\n'
                   '     * unused in vanilla prep -- but our custom cast map sprites render\n'
                   '     * from it, so keep the cast palette ApplyUnitSpritePalettes just\n'
                   '     * loaded instead of blanking it (else the roster goes black). */\n')
    if fill_orig not in prep:
        sys.exit('ERROR: PrepUnit_InitSMS purple-bank fill not in expected form in %s'
                 % PREP_UNITSELECT_C)
    prep = prep.replace(fill_orig, fill_hooked, 1)
    with open(PREP_UNITSELECT_C, 'w', encoding='utf-8') as f:
        f.write(prep)


def _inject_cast_palette(palette_u16, char_slots):
    """Emit gCastMapPalette (the bespoke 16-colour bank) + gMapPaletteOverride (the
    charIds that wear it, 0xFFFF-terminated) into the kept .data file, then patch the
    bmudisp palette hooks. char_slots = portrait-slot names (-> CHARACTER_<SLOT>)."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        wait_c = f.read()
    if 'constants/characters.h' not in wait_c:
        wait_c = wait_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    pal = ', '.join('0x%04X' % c for c in palette_u16)
    ov = '\n'.join('\tCHARACTER_%s,' % s.upper() for s in char_slots)
    wait_c += ('\n/* injected: bespoke cast map-sprite palette (loaded into the purple OBJ\n'
               ' * bank) + the charIds that wear it (0xFFFF-terminated). Non-const so they\n'
               ' * share unit_icon_wait_table\'s kept .data section. */\n'
               'unsigned short gCastMapPalette[16] = { %s };\n' % pal
               + 'unsigned short gMapPaletteOverride[] = {\n' + ov + '\n\t0xFFFF\n};\n')
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(wait_c)
    _inject_palette_bank_hook()


def inject_map_sprites(campaign, verbose=True):
    """Give cast members a custom overworld sprite distinct from their class.

    Two sheets per character, both optional and added one at a time (no asset -> the
    unit keeps its stock-class sprite; stock classes and vanilla enemies untouched):
      * map_sprites/<id>.png      -> IDLE (wait sheet): a custom SMS slot (id 107+)
        plus a GetUnitSMSId per-character override.
      * map_sprites/<id>_mu.png   -> HOVER/WALK (MU sheet, 32x480): a custom move sheet
        plus a GetMuImg per-character override (reuses the class motion script)."""
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    cast = classed_cast(campaign)
    idle = [(uid, slot, cls, sms) for (uid, slot, cls, sms) in cast
            if os.path.isfile(os.path.join(asset_dir, uid + '.png'))]

    # Cold-open guests (PROLOGUE_GUEST_SPRITES) get the same SMS/MU overrides but render
    # through FE8's standard player palette -- so they are kept out of custom_slots (no
    # cast-palette override) below. Their SMS ids continue past the cast's so each guest's
    # wait-table row lands at the index its id names (rows append after the cast's).
    guest_idle, guest_bases = [], {}
    for uid, slot, cls, base in PROLOGUE_GUEST_SPRITES:
        if os.path.isfile(os.path.join(asset_dir, uid + '.png')):
            guest_idle.append((uid, slot, cls, CUSTOM_SMS_BASE + len(idle) + len(guest_idle)))
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
    mu, mu_tmp = [], None
    for uid, slot, cls, sms in idle:
        committed = os.path.join(asset_dir, uid + '_mu.png')
        if os.path.isfile(committed):
            mu.append((uid, slot, cls, committed))
            continue
        if mu_tmp is None:
            mu_tmp = tempfile.mkdtemp(prefix='manchego_mu_')
        src = os.path.join(mu_tmp, uid + '_mu.png')
        nudge = ((load_unit(campaign, uid).get('art') or {}).get('map_sprite') or {}).get(
            'glide_nudge', 0)
        map_sprite_tool.synth_mu_sheet(os.path.join(asset_dir, uid + '.png'),
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
    _inject_idle_sprites(campaign, asset_dir, idle + guest_idle, pointer_externs, guest_bases)
    _inject_mu_sprites(mu + guest_mu, pointer_externs)
    if pointer_externs:
        with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars custom map sprites (#38) */\n'
                    + '\n'.join(pointer_externs) + '\n')

    # Any cast with a custom sprite (idle and/or MU) wears the bespoke cast palette in
    # its own OBJ bank -- its sheet is drawn to the cast-palette indices, so it must be
    # viewed through that palette (decisions.md Art & Audio).
    custom_slots = [slot for _, slot, _, _ in idle]
    custom_slots += [slot for _, slot, _, _ in mu if slot not in custom_slots]
    if custom_slots:
        pal_png = os.path.join(asset_dir, 'cast_palette.png')
        if not os.path.isfile(pal_png):
            sys.exit('ERROR: custom map sprites need campaigns/%s/map_sprites/cast_palette.png'
                     % campaign)
        _inject_cast_palette(_read_cast_palette(pal_png), custom_slots)

    # ch02 green chwinga: reskin minor NPC slots with Sclorbo's chwinga map sprite, tinted
    # by the green faction palette (no bespoke palette -- they're green faction). Runs here
    # because inject_map_sprites owns the gMapSpriteOverride / gMuImgOverride tables.
    _inject_ch02_chwinga_sprites(campaign, verbose=verbose)

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

    sms = _wait_table_len()
    _append_table_rows(UNIT_ICON_WAIT_C, 'unit_icon_wait_table[]',
                       ['\t{0, %s, %s}, // %d chwinga (green NPC)' % (macro, wait_sym, sms)])
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
    slots = [slot for _, slot, _ in CH02_CHWINGA]
    _insert_table_head(UNIT_ICON_WAIT_C, 'gMapSpriteOverride[]',
                       ''.join('\tCHARACTER_%s, %d,\n' % (s.upper(), sms) for s in slots))
    _insert_table_head(UNIT_ICON_MOVE_C, 'gMuImgOverride[]',
                       ''.join('\t{CHARACTER_%s, %s},\n' % (s.upper(), move_sym) for s in slots))
    if verbose:
        print('  chwinga (green NPC) -> idle SMS %d + MU, slots: %s'
              % (sms, ', '.join(slots)))


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


def _inject_idle_sprites(campaign, asset_dir, idle, pointer_externs, guest_bases=None):
    """Wait-table slot + GetUnitSMSId override for each idle (<id>.png) asset."""
    wait_rows, incbin, overrides = [], [], []
    for uid, slot, class_enum, sms in idle:
        # Frame size from the decomp wait table for the donor base -- not guessed.
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(
            _donor_base(campaign, uid, guest_bases))
        macro, fw, fh, nframes = map_sprite_tool.sheet_info(
            os.path.join(asset_dir, uid + '.png'), (dfw, dfh))
        sym = 'unit_icon_wait_manchego_%s_sheet' % uid.replace('-', '_')
        shutil.copyfile(os.path.join(asset_dir, uid + '.png'),
                        os.path.join(WAIT_GFX_DIR, sym + '.png'))
        wait_rows.append('\t{0, %s, %s}, /* %d %s */' % (macro, sym, sms, uid))
        incbin += ['\t.global %s' % sym, '%s:' % sym,
                   '\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"' % sym,
                   '\t.align 2, 0']
        pointer_externs.append('extern char %s[];' % sym)
        overrides.append('\tCHARACTER_%s, %d,' % (slot.upper(), sms))

    _append_table_rows(UNIT_ICON_WAIT_C, 'unit_icon_wait_table[]', wait_rows)
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
# (-> a new animId), then -- so generic/enemy archers stay vanilla -- give the unit a
# stat-identical CLONE of the donor class (clone_into) whose private AnimConf selects the new
# animId, and deploy the unit as that clone (deploy_class_for). Nothing vanilla is overwritten
# (donor class + AnimConf byte-unchanged). Reversible: the patched files restore each build.

# donor 'clone_from' -> (FE donor class enum, the AnimConf weapon entry to repoint in the clone).
BANIM_DONORS = {'archer': ('CLASS_ARCHER', '0x0100 | ITYPE_BOW')}


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
            if rgba[3] > 0 and rgba[:3] not in pal:
                pal.append(rgba[:3])
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


def inject_battle_anims(campaign, verbose=True):
    """Generate + inject each unit's faked battle animation (additive donor-prime, #65).

    ADDING A UNIT (the repeatable how): give its YAML a `battle_anim:` block --
        clone_from: archer                  # donor class: timing/effects/modes + the weapon slot
        clone_into: CLASS_<FREE_SLOT>       # a FREE class enum -> this unit's PRIVATE clone class
        abbr: <stem>                        # banim asset stem (<=12 chars)
        frames: [<unit>/ready.png, <unit>/windup.png, <unit>/peak.png]  # 1-3, Ready->Windup->Peak
    Frames: BOX-descale the hi-res (e.g. 1920x1080) source poses onto a ~88x64 canvas with a COMMON
    feet-anchor + a protected ~15-colour palette. NEVER re-shrink an already-small frame (non-integer
    re-shrink looks muddy) -- to rescale a unit, re-descale from the hi-res master.

    This APPENDS a banim_data[] row (table self-sizes) and CLONES the donor class into clone_into with
    its OWN AnimConf, so the donor class + generic/enemy units of it stay byte-vanilla -- only this
    unit (deployed AS the clone via deploy_class_for) shows the custom anim. Stats ride STAT_DONOR/
    BASE_DONOR/GROWTH_DONOR; PORTRAIT_MAP ties the unit id -> its vanilla character slot.

    !! OFF-BY-ONE: the clone's AnimConf `.index` MUST be `anim_id + 1` (GetBattleAnimationId returns
       idx - 1). Get it wrong and a PURPLE DRAGON renders instead of the unit.
    Decisions/rationale: decisions.md (Art & Audio, the additive clone-class call).
    """
    from PIL import Image
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
        donor_class, wtype = BANIM_DONORS[clone_from]
        abbr = cfg.get('abbr') or (uid.replace('-', '').replace('prof', '')[:5] + '_ar1')
        frame_imgs = [Image.open(os.path.join(anim_dir, p)).convert('RGBA')
                      for p in cfg['frames']]
        palette = _banim_palette(frame_imgs)
        res = ref_to_battleframe.build_battle_anim(abbr, frame_imgs, palette)

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

        # 4. ADDITIVE isolation: instead of repointing the shared donor class, give the unit
        #    a stat-identical CLONE class whose own AnimConf selects the new animId. The donor
        #    class + its AnimConf stay byte-vanilla, so every generic/enemy unit of that class
        #    keeps the stock anim; only this unit (deploy_class_for -> clone_into) changes.
        clone_slot = cfg.get('clone_into')
        if not clone_slot:
            sys.exit('ERROR: battle_anim %s: missing clone_into (the Archer-clone slot)' % uid)
        new_conf = 'AnimConf_%s' % abbr
        src_conf = _class_field_symbol(donor_class, 'pBattleAnimDef')  # e.g. AnimConf_088AF150
        # 4a. a private AnimConf = copy of the donor's, with the weapon entry -> new animId.
        #     NOTE: AnimConf `.index` is animId+1 -- GetBattleAnimationId returns `idx - 1`
        #     (vanilla archer bow .index 0x26 -> animId 0x25). So encode anim_id + 1.
        with open(BANIMCONF_C, encoding='utf-8') as f:
            conf = f.read()
        conf = banim_clone_conf(conf, src_conf, new_conf, wtype, anim_id + 1)
        with open(BANIMCONF_C, 'w', encoding='utf-8') as f:
            f.write(conf)
        with open(BANIM_EKRBATTLE_H, 'a', encoding='utf-8') as f:
            f.write('extern CONST_DATA struct BattleAnimDef %s[]; /* Manchego Stars #65 */\n'
                    % new_conf)
        # 4b. clone the donor ClassData into clone_slot (full copy = identical stats/combat),
        #     repoint .number + .pBattleAnimDef -> the private AnimConf
        with open(CLASSES_C, encoding='utf-8') as f:
            ctext = f.read()
        bs, be = _find_brace_block(ctext, '[%s - 1]' % donor_class, CLASSES_C)
        body = ctext[bs:be]
        body = _set_field(body, 'number', clone_slot, CLASSES_C, donor_class)
        body = _set_field(body, 'pBattleAnimDef', new_conf, CLASSES_C, donor_class)
        ctext = _replace_brace_block(ctext, '[%s - 1]' % clone_slot, body, CLASSES_C)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(ctext)

        if verbose:
            print('  %-14s = banim %s (animId 0x%X); clone %s -> %s (%s.%s)'
                  % (uid, abbr, anim_id, donor_class, clone_slot, new_conf, wtype))


def _class_field_symbol(class_enum, field):
    """Read a symbol-valued field (e.g. .pBattleAnimDef = AnimConf_X) from gClassData."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    m = re.search(r'\.' + field + r'\s*=\s*(\w+)', text[bs:be])
    if not m:
        sys.exit('ERROR: .%s symbol not found in gClassData[%s]' % (field, class_enum))
    return m.group(1)


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

            sms_id = _wait_table_len()
            _append_table_rows(UNIT_ICON_WAIT_C, 'unit_icon_wait_table[]',
                               ['\t{0, %s, %s}, // %d %s (reskin)' % (macro, wait_sym, sms_id, sprite)])
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

# Registered as asset-table entries (label -> decomp incbin source we copy in).
WINTER_TILESET = 'snowy-bern'
WINTER_ASSETS = [  # (asset-table label, decomp filename, incbin path)
    ('ObjectTypeSnow',        'ObjectTypeSnow.4bpp',         'graphics/map/ObjectTypeSnow.4bpp.lz'),
    ('MapPaletteSnow',        'MapPaletteSnow.gbapal',       'graphics/map/MapPaletteSnow.gbapal'),
    ('TileConfigurationSnow', 'TileConfigurationSnow.bin',   'graphics/map/TileConfigurationSnow.bin.lz'),
]
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


def inject_winter_tileset(campaign, verbose=True):
    """Register the winter tileset (#41) + a flat test layout and repoint the test
    chapter at them, so a build load-tests the tileset in-engine (#40)."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    ts_dir = os.path.join(maps_dir, 'tilesets', WINTER_TILESET)

    # 1. Copy the tileset pieces into the decomp (raw; the Makefile %.lz rule compresses
    #    gfx + config, palette stays raw like vanilla MapPaletteN.gbapal).
    for label, fname, _ in WINTER_ASSETS:
        src = os.path.join(ts_dir, {'ObjectTypeSnow': '%s.4bpp' % WINTER_TILESET,
                                    'MapPaletteSnow': '%s.gbapal' % WINTER_TILESET,
                                    'TileConfigurationSnow': '%s.bin' % WINTER_TILESET}[label])
        shutil.copyfile(src, os.path.join(MAP_GFX_DIR, fname))

    # 2. Copy the test layout source (.mar + .json -> Makefile mar_to_map -> .bin -> .lz).
    layout_label, stem = WINTER_TEST_LAYOUT
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (layout_label, ext)))

    # 3. Define the asset symbols (incbin) at the end of const_data_chapter_maps.s.
    incbin = ['\n/* Manchego Stars winter tileset + test layout (#40/#41) */']
    for label, _, path in WINTER_ASSETS:
        incbin += ['\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
                   '\t.incbin "%s"' % path]
    incbin += ['\t.align 2, 0', '\t.global %s' % layout_label, '%s:' % layout_label,
               '\t.incbin "graphics/map/layout/%s.bin.lz"' % layout_label]
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join(incbin) + '\n')

    # 4. Append them to gChapterDataAssetTable; the first lands at the prior entry count.
    labels = [a[0] for a in WINTER_ASSETS] + [layout_label]
    base = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', labels)
    idx = {label: base + i for i, label in enumerate(labels)}

    # 5. Repoint the TEST chapter (the inject_test_chapter target) at the winter tileset
    #    + flat layout. obj2/anim/changes off -> the flat field needs none.
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    cmap = settings['chapters'][TEST_CHAPTER_INDEX]['map']
    cmap.update({'obj1Id': idx['ObjectTypeSnow'], 'obj2Id': 0,
                 'paletteId': idx['MapPaletteSnow'], 'tileConfigId': idx['TileConfigurationSnow'],
                 'mainLayerId': idx[layout_label], 'objAnimId': 0, 'paletteAnimId': 0,
                 'changeLayerId': 0})
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    if verbose:
        print('  %s tileset -> asset table [%d..%d]; test chapter (idx %d) repointed'
              % (WINTER_TILESET, base, base + len(labels) - 1, TEST_CHAPTER_INDEX))


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
    # (Hlin/Warrior) -- the vanilla Prologue Seth+Eirika dynamic. (Difficulty lives in the
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
    label, stem = PROLOGUE_LAYOUT
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (label, ext)))
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars prologue layout (#20) */',
            '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % label]) + '\n')
    layout_idx = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [label])
    obj_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'ObjectTypeSnow')
    pal_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'MapPaletteSnow')
    cfg_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'TileConfigurationSnow')
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
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    # 2. Rewrite the two prologue rosters. redaCount=0 places units statically at
    #    xPosition/yPosition (like inject_test_chapter); the boss rides the ONEILL slot so
    #    its CA_BOSS attribute makes DefeatBoss fire on death. Positions/levels/items from
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
    #    on EVFLAG_DEFEAT_BOSS, which the engine sets when a CA_BOSS unit (Sephek, on the
    #    ONEILL slot) dies -> runs the ending scene; CauseGameOverIfLordDies = AFEV on
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
    title_png = os.path.join(DECOMP, 'graphics', 'chap_title',
                             'chap_title_%d.png' % host['chapTitleId'])
    gen_chapter_title.compose_title('Prologue: ' + chap['title']).save(title_png)
    for stale in (title_png[:-4] + '.4bpp', title_png[:-4] + '.4bpp.lz'):
        if os.path.exists(stale):
            os.remove(stale)

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
    #    whose trailing REMA clears all faces (scene.c sub_800E640) -> a fresh 4-face
    #    budget per beat. TWO SIDES: the quest-givers stand on the RIGHT (Hlin mid-right,
    #    Scramsax far-right, Hruna right) and the party on the LEFT. The roll-call rotates
    #    one PC at a time through the mid-left spotlight (eviction); monologue beats PRELOAD
    #    a few PCs as silent listeners on the left so Hlin/RBG address a populated room
    #    instead of empty air, and the haggle puts Hruna across from RBG. Hlin's final
    #    "who leads?" line stays in the scene (end of beat E, at the Northlook); the
    #    lord-select menu then plays over its own scenic BG (not the battle map).
    b1_script = next(e for e in chap['events']
                     if e['trigger'] == 'chapter_start')['script']
    b1_card = next(v for e in b1_script for k, v in e.items() if k == 'location_card')
    b1_beats = [[]]
    for entry in b1_script:
        (k, v), = entry.items()
        if k == 'location_card':
            continue
        if k == 'beat_break':
            b1_beats.append([])
            continue
        b1_beats[-1].append(entry)
    if len(b1_beats) != len(CH01_BEAT1_MSGS):
        sys.exit('ERROR: ch01 Beat 1 split into %d beats; expected %d (check '
                 'beat_break markers in the YAML)' % (len(b1_beats), len(CH01_BEAT1_MSGS)))

    def b1_fid(spk):
        if spk == 'hlin':
            return _fid_tag(PROLOGUE_HLIN_SLOT)
        if spk == 'scramsax':
            return _fid_tag(PROLOGUE_SCRAMSAX_SLOT)
        if spk == 'hruna':
            return _fid_tag('VILLAGER_WOMAN')
        if spk in PORTRAIT_MAP:
            return _fid_tag(PORTRAIT_MAP[spk].upper())
        sys.exit('ERROR: ch01 Beat 1 unknown speaker %r' % spk)
    # Podium geometry (gTalkFaceHPosLut, scene.c, px = x*8; faces are 96px = 12 tiles):
    # FarLeft 24 | MidLeft 48 | Left 72 | Right 168 | MidRight 192 | FarRight 216.
    # Two faces only avoid overlap when >=96px apart, so the clean "two-shot" is
    # MidLeft <-> MidRight (144px). Speakers therefore default to the mid-left podium
    # and Hlin anchors mid-right; everyone rotating through one inner podium keeps the
    # stage to two non-overlapping faces (Nicolas, 2026-06-16: Hlin/Scramsax & the
    # 3-stack were too crowded). Silent listeners fill the OUTER podiums where a touch
    # of overlap reads as "a couple standing together."
    b1_home = {'hlin': '[OpenMidRight]'}

    def b1_stage(beat, overrides=None):
        ov = overrides or {}
        return {k: (ov.get(k, b1_home.get(k, '[OpenMidLeft]')), b1_fid(k))
                for e in beat for k in e}
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
    end_script = next(e for e in chap['events']
                      if e['trigger'] == 'chapter_end')['script']
    end_card = next(v for e in end_script for k, v in e.items() if k == 'location_card')
    end_beats = [[]]
    for entry in end_script:
        (k, v), = entry.items()
        if k == 'location_card':
            continue
        if k == 'beat_break':
            end_beats.append([])
            continue
        end_beats[-1].append(entry)
    if len(end_beats) != len(CH01_ENDING_MSGS):
        sys.exit('ERROR: ch01 ending split into %d beats; expected %d (check '
                 'beat_break markers in the YAML)' % (len(end_beats), len(CH01_ENDING_MSGS)))

    def end_fid(spk):
        if spk == 'narration':                  # faceless stage-business box (no portrait)
            return None
        if spk in PORTRAIT_MAP:
            return _fid_tag(PORTRAIT_MAP[spk].upper())
        if spk in GUEST_PORTRAIT_MAP:           # duvessa/hruna/baxby cutscene faces
            return _fid_tag(GUEST_PORTRAIT_MAP[spk].upper())
        sys.exit('ERROR: ch01 ending unknown speaker %r' % spk)
    # Duvessa hosts from mid-right (like Hlin in Beat 1); everyone else defaults mid-left.
    # Per-beat overrides put the OTHER speaker opposite her for a clean two-shot: Hruna
    # (C) and Meesmickle (D) take mid-right; in E, Baxby takes mid-right -- evicting
    # Duvessa's face there (a [ClearFace] step-out) as she gestures to the market and the
    # bird steps forward. Marty stays mid-left across E.
    end_home = {'duvessa': '[OpenMidRight]'}

    def end_stage(beat, overrides=None):
        ov = overrides or {}
        return {k: (ov.get(k, end_home.get(k, '[OpenMidLeft]')), end_fid(k))
                for e in beat for k in e}
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
    label, stem = CH01_LAYOUT
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (label, ext)))
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars ch01 layout (#21) */',
            '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % label]) + '\n')
    layout_idx = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [label])
    obj_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'ObjectTypeSnow')
    pal_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'MapPaletteSnow')
    cfg_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'TileConfigurationSnow')
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    host = settings['chapters'][CH01_HOST_INDEX]
    seize_goal = settings['chapters'][1]['goal']
    if seize_goal.get('windowDataType') != 'seize':
        sys.exit('ERROR: slot 1 goal is not the vanilla Seize template -- '
                 'inject_ch01 must run BEFORE inject_prologue')
    host['map'].update({'obj1Id': obj_idx, 'obj2Id': 0, 'paletteId': pal_idx,
                        'tileConfigId': cfg_idx, 'mainLayerId': layout_idx,
                        'objAnimId': 0, 'paletteAnimId': 0, 'changeLayerId': 0})
    host['goal'] = dict(seize_goal)
    # The prep-screen header reads "Chapter NN" from prepScreenNumber, not the
    # slot index. It is a double-wide glyph index: vanilla slots carry exactly
    # 2 * chapter number (slot1=2, slot2=4, ... both ch5 and ch5x = 10).
    host['prepScreenNumber'] = chap['chapter_number'] * 2
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    # 2. Rosters (events_udefs.c). Four tables, all reusing vanilla Ch2 symbols so no
    #    extern surgery is needed (scripts/eventinfo already declare them):
    #    - UnitDef_Event_Ch2Ally: the 4-slot deploy template = THE CAP. Never LOADed;
    #      the prep flow reads its entry count (cap) and positions (deploy tiles).
    #    - UnitDef_088B440C: the cast join-LOAD (whole roster enters the party at the
    #      Northlook; the engine benches everyone past the cap).
    #    - UnitDef_088B4344: the 7 initial goblins. UnitDef_088B44AC: the 3 west
    #      reinforcements (turn 3).
    cast = []
    cast_names = []  # parallel to cast: lord-select menu/confirm display names (#42)
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if class_enum not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (unit %s)' % (class_enum, unit_id))
        cast.append((unit_id, slot, class_enum, deploy_class_for(unit),
                     int(unit.get('fe_stats', {}).get('level', 1))))
        cast_names.append(display_name(unit))
    if len(cast) > len(LORDSEL_CONFIRM_MSGS):
        sys.exit('ERROR: %d lord candidates > %d reserved confirm text ids'
                 % (len(cast), len(LORDSEL_CONFIRM_MSGS)))
    if len(cast) > len(CH01_JOIN_POSITIONS):
        sys.exit('ERROR: %d classed cast > %d ch01 join positions'
                 % (len(cast), len(CH01_JOIN_POSITIONS)))
    leader = 'CHARACTER_%s' % cast[0][1].upper()

    def ally_entry(slot, class_enum, level, x, y, items, comment):
        return ('    {\n'
                '        .charIndex = CHARACTER_%s,%s\n'
                '        .classIndex = %s,\n'
                '        .leaderCharIndex = %s,\n'
                '        .allegiance = FACTION_ID_BLUE,\n'
                '        .level = %d,\n'
                '        .xPosition = %d,\n'
                '        .yPosition = %d,\n'
                '        .redaCount = 0,\n'
                '        .items = { %s },\n'
                '    },' % (slot.upper(), comment, class_enum, leader, level, x, y, items))

    # classIndex rides the DEPLOY class (dce -- the Archer-clone for RBG, #65); items/loadout
    # still come from the real vanilla class (ce). For most units dce == ce.
    join = [ally_entry(slot, dce, lv, x, y, ', '.join(CLASS_LOADOUT[ce]),
                       ' /* %s */' % uid)
            for (uid, slot, ce, dce, lv), (x, y) in zip(cast, CH01_JOIN_POSITIONS)]
    deploy = [ally_entry(slot, dce, lv, x, y, '0',
                         ' /* deploy slot %d (cap template, never LOADed) */' % i)
              for i, ((uid, slot, ce, dce, lv), (x, y))
              in enumerate(zip(cast[:len(chap['deploy_slots'])], chap['deploy_slots']))]
    if len(deploy) != chap['deploy_limit']:
        sys.exit('ERROR: deploy_slots (%d) != deploy_limit (%d) in ch01 YAML'
                 % (len(deploy), chap['deploy_limit']))

    def enemy_entry(char, class_enum, level, autolevel, x, y, items, ai, comment):
        return ('    {\n'
                '        .charIndex = %s,%s\n'
                '        .classIndex = %s,\n'
                '%s'
                '        .allegiance = FACTION_ID_RED,\n'
                '        .level = %d,\n'
                '        .xPosition = %d,\n'
                '        .yPosition = %d,\n'
                '        .redaCount = 0,\n'
                '        .items = { %s },\n'
                '        .ai = %s,\n'
                '    },' % (char, comment, class_enum,
                           '        .autolevel = 1,\n' if autolevel else '',
                           level, x, y, items, ai))

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
        enemies.append(enemy_entry(
            '0x80', grunt_class(spear['class']), spear['level'], True, x, y,
            CH01_ITEM_IDS[spear['inventory'][0]['id']], CH01_AI[spear['ai_pattern']],
            ' /* goblin spear -- camp approach */'))
    for x, y in axe['positions']:
        enemies.append(enemy_entry(
            '0x80', grunt_class(axe['class']), axe['level'], True, x, y,
            CH01_ITEM_IDS[axe['inventory'][0]['id']], CH01_AI[axe['ai_pattern']],
            ' /* goblin raider -- mid-trail pursuer */'))
    cx, cy = chief['position']
    # The iron-ingots MacGuffin stays narrative (no FE8 item exists for it yet);
    # recovery is told in the ending scene. The chief mirrors Breguet 1:1: his slot's
    # vanilla boss bases, no autolevel, lv4, attack-in-place AI, ON the seize tile.
    enemies.append(enemy_entry(
        'CHARACTER_%s' % CH01_BOSS_SLOT, CH01_CLASS_IDS[chief['class']],
        chief['level'], False, cx, cy,
        CH01_ITEM_IDS[chief['inventory'][0]['id']], CH01_AI[chief['ai_pattern']],
        ' /* goblin chief -- boss, holds the seize tile */'))
    reinforce = []
    for cls, (x, y) in zip(reinf['composition'], reinf['positions']):
        reinforce.append(enemy_entry(
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
            '    },' % (vanilla_name_text_id(slot), uid, i))
    menu_code = (
        '/* ==== Lord select (#42, build-generated): pre-preparations leader menu ====\n'
        '   Route-split menu clone (cf. CallRouteSplitMenu, ch8-eventscript.h). The\n'
        '   pick is stored as permanent flag 0x%X + item index and read back by\n'
        '   LordSelect_GetPid (eventinfo.c) to drive force-deploy, Seize, and the\n'
        '   lord-death game over. One confirm text per candidate (dead vanilla\n'
        '   slot-2 message ids). */\n'
        '\n'
        '#include "uimenu.h"\n'
        '#include "fontgrp.h"\n'
        '#include "hardware.h"\n'
        '#include "uiutils.h"\n'
        '\n'
        'extern const u16 gLordSelectCandidates[]; /* events_udefs.c */\n'
        '\n'
        'static CONST_DATA u16 sLordSelectConfirmMsg[] = { %s };\n'
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
        '    .rect = {9, 1, 12, 0},\n'
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
        '    StartMenu(&MenuDef_LordSelect, proc);\n'
        '}\n'
        '\n'
        % (LORDSEL_FLAG_BASE, ', '.join('0x%X' % m for m in
                                        LORDSEL_CONFIRM_MSGS[:len(cast)]),
           LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE, '\n'.join(items)))
    with open(CH2_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    script = menu_code + script
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
        '       over the BACG on BG3; CallLordSelectMenu keeps BG2 (map) off. */\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(%s)\n'
        '    FADU(16)\n'
        '    EVBIT_MODIFY(0x4)\n'
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
        '    EVBIT_MODIFY(0x0)\n'
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
        '    FADU(16) /* reveal the trail map (cf. vanilla Ch4) */\n'
        '    CALL(EventScr_08591FD8) /* preparations (PREP, event cmd 0x3E) */\n'
        '    ENUT(8)\n'
        '    EVBIT_T(7)\n'
        '    ENDA\n}' % (CH01_LORDSEL_BG, CH01_HOST_INDEX), CH2_EVENTSCRIPT_H)
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
    # bodies + staging are built in step 0b/step 6. The scene plays over the vanilla
    # BG_NORMAL_VILLAGE (we tried winterizing it but a palette swap just washes it out and
    # no clean FE8 snow-village BG was available, so we use it as-is; Nicolas 2026-06-17).
    # ch02 isn't hosted yet, so instead of MNC2'ing onto a leftover vanilla map the
    # ending lands on the reusable dev placeholder (dev_placeholder_scene): RBG's
    # "still under construction" cheese pun, then back to title. Swap to MNC2(ch02 slot)
    # when ch02 lands.
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
        '    BACG(BG_NORMAL_VILLAGE) /* Bryn Shander -- vanilla village BG (winterize not worth it; Nicolas, 2026-06-17) */\n'
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
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n'
    if bq.count(head) != 1:
        sys.exit('ERROR: gDefeatTalkList head not in expected form in %s'
                 % BATTLEQUOTES_C)
    bq = bq.replace(head, head + quote + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)

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
                     name_message_body('Seize camp'))
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
    for i, (msg_id, beat) in enumerate(zip(CH01_ENDING_MSGS, end_beats)):
        # Faceless-narration beats ride the opaque, auto-centered SOLOTEXTBOXSTART box
        # (#58): wrap at the on-map width so the centered box fits the 240px screen (42
        # overflows it); faced beats use the full-screen scenic wrap.
        w = 28 if _beat_is_narration(beat) else 42
        set_message_body(lines, msg_id, _script_to_message(
            beat, end_stage(beat, end_overrides[i]), width=w, preload=end_preload[i]))
    # Beat 1 (#21): the Northlook opening. Card + one message per beat (A-E), rendered
    # from the chapter YAML's locked script with the scenic full-screen wrap width and
    # the per-beat two-sided staging + silent listeners built in step 0. Each beat rides
    # its own Text()/REMA, so the 4-face budget resets per beat.
    set_message_body(lines, CH01_BEAT1_CARD_MSG, name_message_body(b1_card))
    for i, (msg_id, beat) in enumerate(zip(CH01_BEAT1_MSGS, b1_beats)):
        set_message_body(lines, msg_id, _script_to_message(
            beat, b1_stage(beat, b1_overrides[i]), width=42, preload=b1_preload[i]))
    # Lord select (#42): Hlin's "who leads?" already lands in beat E (at the Northlook),
    # so the menu opens directly over its scenic BG -- no separate prompt. Per-candidate
    # confirm texts keep the vanilla route-split shape (cf. MSG_C14/C17/C18) incl. the
    # odd-printable-count [.] parity pad.
    for i, name in enumerate(cast_names):
        q = 'Will %s lead the party?' % name
        set_message_body(lines, LORDSEL_CONFIRM_MSGS[i], '%s%s[LF]\n[Yes][X]'
                         % (q, '[.]' if len(q) % 2 else ''))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 6a. Title card image (the intro/status banner is a 4bpp image, not text).
    title_png = os.path.join(DECOMP, 'graphics', 'chap_title',
                             'chap_title_%d.png' % host['chapTitleId'])
    gen_chapter_title.compose_title('Ch.1: ' + chap['title']).save(title_png)
    for stale in (title_png[:-4] + '.4bpp', title_png[:-4] + '.4bpp.lz'):
        if os.path.exists(stale):
            os.remove(stale)

    if verbose:
        print('  ch01 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'deploy cap %d + PREP (vanilla Ch4+ idiom)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH01_HOST_INDEX, len(deploy)))
        print('  rosters: %d cast join, %d goblins + chief on (%d,%d) [Seize], '
              '%d west reinforcements turn %d'
              % (len(cast), len(enemies) - 1, cx, cy, len(reinforce),
                 reinf['spawn_turn']))


def inject_ch02(campaign, verbose=True):
    """Wire Ch2 "Cold Welcome" (#22) onto chapter slot 3 (ch01's MNC2(0x3) target).

    Simpler than inject_ch01: the party PERSISTS from ch01 (no cast re-LOAD, no
    lord-select menu), and the win is DefeatAll (no Seize). The slot-3 host goal is
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
    def split_beats(trigger):
        scr = next(e for e in chap['events'] if e.get('trigger') == trigger)['script']
        card = next((v for e in scr for k, v in e.items() if k == 'location_card'), None)
        beats = [[]]
        for entry in scr:
            (k, v), = entry.items()
            if k == 'location_card':
                continue
            if k == 'beat_break':
                beats.append([])
                continue
            beats[-1].append(entry)
        return card, beats

    op_card, op_beats = split_beats('chapter_start')
    end_card, end_beats = split_beats('chapter_end')
    bark = next(e for e in chap['events']
                if e.get('trigger') == 'turn_start' and e.get('turn') == 3)['script']
    tutorial = next(e for e in chap['events']
                    if e.get('trigger') == 'turn_start' and e.get('turn') == 1)['script']
    if len(op_beats) != len(CH02_OPENING_MSGS):
        sys.exit('ERROR: ch02 opening split into %d beats; expected %d (check '
                 'beat_break markers)' % (len(op_beats), len(CH02_OPENING_MSGS)))
    if len(end_beats) != len(CH02_ENDING_MSGS):
        sys.exit('ERROR: ch02 ending split into %d beats; expected %d (check '
                 'beat_break markers)' % (len(end_beats), len(CH02_ENDING_MSGS)))
    if len(tutorial) != len(CH02_TUTORIAL_MSGS):
        sys.exit('ERROR: ch02 turn-1 tutorial has %d lines; expected %d '
                 '(zip would silently drop the extra)' % (len(tutorial), len(CH02_TUTORIAL_MSGS)))

    def cut_fid(spk):
        if spk == 'narration':                 # faceless stage-business box (#58)
            return None
        if spk == 'vellynne':                  # recurring NPC: placeholder face (#19)
            return _fid_tag(CH02_VELLYNNE_SLOT)
        if spk == 'targos-fisher':             # generic villager mug
            return CH02_FISHER_FID
        if spk in PORTRAIT_MAP:
            return _fid_tag(PORTRAIT_MAP[spk].upper())
        sys.exit('ERROR: ch02 unknown cutscene speaker %r' % spk)

    # Vellynne anchors mid-right (the quest-giver, cf. Hlin/Duvessa); everyone else
    # speaks from mid-left. The ending beats are single-speaker each, so mid-left is
    # enough (no two-shots, no preloads -> no REMA face-flashing, cf. inject_ch01).
    op_home = {'vellynne': '[OpenMidRight]'}

    def stage(beat, home):
        return {k: (home.get(k, '[OpenMidLeft]'), cut_fid(k))
                for e in beat for k in e}

    # 1. Map: register the painted layout, point slot 3 at it + the winter tileset, and
    #    swap the host goal to vanilla slot-4's defeat_all template (cf. inject_ch01 step 1).
    label, stem = CH02_LAYOUT
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (label, ext)))
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars ch02 layout (#22) */',
            '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % label]) + '\n')
    layout_idx = _append_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [label])
    obj_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'ObjectTypeSnow')
    pal_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'MapPaletteSnow')
    cfg_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', 'TileConfigurationSnow')
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    host = settings['chapters'][CH02_HOST_INDEX]
    defeat_goal = settings['chapters'][4]['goal']
    if defeat_goal.get('windowDataType') != 'defeat_all':
        sys.exit('ERROR: slot 4 goal is not the vanilla defeat_all template '
                 '(needed as the ch02 DefeatAll donor)')
    host['map'].update({'obj1Id': obj_idx, 'obj2Id': 0, 'paletteId': pal_idx,
                        'tileConfigId': cfg_idx, 'mainLayerId': layout_idx,
                        'objAnimId': 0, 'paletteAnimId': 0, 'changeLayerId': 0})
    host['goal'] = dict(defeat_goal)
    host['prepScreenNumber'] = chap['chapter_number'] * 2   # "Chapter 2" header (2*N)
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    # 2. Rosters (events_udefs.c). Four tables, reusing vanilla Ch3 symbols (already
    #    declared in eventcall.h, so no extern surgery):
    #    - UnitDef_Event_Ch3Ally: the 5-slot deploy template = THE CAP. Never LOADed;
    #      the prep flow reads its entry count (cap) + positions (deploy tiles). The
    #      party itself persists from ch01 (no join-LOAD).
    #    - UnitDef_088B463C: the RED raider band (Beginning-scene LOAD1) -- vanilla Ch2's
    #      exact mix, reflavored chardalyn berserkers. 0x8e = generic autolevelled trash;
    #      Grukk rides the vanilla Bone slot, Halvar the Bazba slot.
    #    - UnitDef_088B4718: the 3 GREEN chwinga (LOAD1 at chapter start, green from .allegiance;
    #      was vanilla Colm's green table). Distinct NPC slots so CHECK_ALIVE tracks each.
    #    - UnitDef_088B4758: the turn-3 RED reinforcement pair (the empty vanilla table;
    #      088B4718 is now the chwinga). Vanilla 088B4470 mix = one L2 + one L3 brigand.
    cast = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        cast.append((unit_id, slot, class_enum,
                     int(unit.get('fe_stats', {}).get('level', 1))))
    if len(cast) < chap['deploy_limit']:
        sys.exit('ERROR: %d classed cast < ch02 deploy_limit %d'
                 % (len(cast), chap['deploy_limit']))
    leader = 'CHARACTER_%s' % cast[0][1].upper()

    def ally_entry(slot, class_enum, level, x, y, comment):
        return ('    {\n'
                '        .charIndex = CHARACTER_%s,%s\n'
                '        .classIndex = %s,\n'
                '        .leaderCharIndex = %s,\n'
                '        .allegiance = FACTION_ID_BLUE,\n'
                '        .level = %d,\n'
                '        .xPosition = %d,\n'
                '        .yPosition = %d,\n'
                '        .redaCount = 0,\n'
                '        .items = { 0 },\n'
                '    },' % (slot.upper(), comment, class_enum, leader, level, x, y))

    deploy_slots = chap['deploy_slots']
    if len(deploy_slots) != chap['deploy_limit']:
        sys.exit('ERROR: ch02 deploy_slots (%d) != deploy_limit (%d)'
                 % (len(deploy_slots), chap['deploy_limit']))
    deploy = [ally_entry(slot, ce, lv, x, y,
                         ' /* deploy slot %d (cap template, never LOADed) */' % i)
              for i, ((uid, slot, ce, lv), (x, y))
              in enumerate(zip(cast[:chap['deploy_limit']], deploy_slots))]

    def enemy_entry(char, class_enum, level, autolevel, x, y, items, ai, comment,
                    itemdrop=False):
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

    def green_entry(slot, level, x, y, items, ai, comment):
        return ('    {\n'
                '        .charIndex = CHARACTER_%s,%s\n'
                '        .classIndex = %s,\n'
                '        .autolevel = 1,\n'          # lean on the pegasus class curve (bases = tuning checkpoint)
                '        .allegiance = FACTION_ID_GREEN,\n'
                '        .level = %d,\n'
                '        .xPosition = %d,\n'
                '        .yPosition = %d,\n'
                '        .redaCount = 0,\n'
                '        .items = { %s },\n'
                '        .ai = %s,\n'
                '    },' % (slot.upper(), comment, CH02_CLASS_IDS['pegasus_knight'],
                           level, x, y, items, ai))

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
        enemies.append(enemy_entry(CH02_GENERIC_PID, brig, raider['level'], True, x, y,
                                   axe, CH02_AI['aggressive'], ' /* chardalyn berserker */'))
    for x, y in scavenger['positions']:
        enemies.append(enemy_entry(CH02_GENERIC_PID, brig, scavenger['level'], True, x, y,
                                   '%s, %s' % (axe, vuln), CH02_AI['aggressive'],
                                   ' /* chardalyn scavenger -- drops the vulnerary */',
                                   itemdrop=True))
    for x, y in skirmisher['positions']:
        enemies.append(enemy_entry(CH02_GENERIC_PID, brig, skirmisher['level'], True, x, y,
                                   axe, CH02_AI['aggressive'], ' /* chardalyn skirmisher (L2) */'))
    for x, y in archer['positions']:
        enemies.append(enemy_entry(CH02_GENERIC_PID, arch, archer['level'], True, x, y,
                                   bow, CH02_AI['aggressive'],
                                   ' /* chardalyn hunter (archer) -- hard-counters the pegasi */'))
    gx, gy = grukk['position']
    enemies.append(enemy_entry('CHARACTER_%s' % CH02_MINIBOSS_SLOT, brig, grukk['level'],
                               False, gx, gy, axe, CH02_AI['hold_position'],
                               ' /* Grukk the Bruiser -- miniboss, fixed bases (Bone slot) */'))
    hx, hy = halvar['position']
    enemies.append(enemy_entry('CHARACTER_%s' % CH02_BOSS_SLOT, brig, halvar['level'],
                               True, hx, hy, steel, CH02_AI['hold_position'],
                               ' /* Halvar the Raider Captain -- boss, steel axe (Bazba slot) */'))

    # 2b. GREEN chwinga (088B4718) -- the protect layer; positions + per-survivor gift
    #     come from the YAML deployment.green_allies (id order matches CH02_CHWINGA).
    chwinga_by_id = {g['id']: g for g in chap['deployment']['green_allies']}
    chwinga = [green_entry(slot, chwinga_by_id[uid]['level'],
                           chwinga_by_id[uid]['position'][0], chwinga_by_id[uid]['position'][1],
                           lance, CH02_AI['cautious'], ' /* chwinga %s (%s) */' % (uid, gift))
               for uid, slot, gift in CH02_CHWINGA]

    # 2c. RED reinforcements (088B4758) -- vanilla 088B4470 mix: one L2 + one L3, turn 3.
    reinforce = [enemy_entry(CH02_GENERIC_PID, brig, lv, True, x, y, axe,
                             CH02_AI['reinforce'], ' /* rear raider L%d, turn %d */'
                             % (lv, reinf['trigger_turn']))
                 for (x, y), lv in zip(reinf['positions'], reinf['levels'])]

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    for marker, entries in (
            ('UnitDef_Event_Ch3Ally[] =', deploy),
            ('UnitDef_088B463C[] =', enemies),
            ('UnitDef_088B4718[] =', chwinga),
            ('UnitDef_088B4758[] =', reinforce)):
        block = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'
        udefs = _replace_brace_block(udefs, marker, block, EVENTS_UDEFS_C)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Event lists (ch3-eventinfo.h). Turn: the rear wolves on turn 3 (FACTION_ID_BLUE
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
        '    FADI(16) /* fade the scenic BG out */\n'
        '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin */\n'
        '    LOMA(0x%X) /* RestartBattleMap -- build the ch02 map fresh (cf. inject_ch01) */\n'
        '    LOAD1(0x1, UnitDef_088B463C) /* the RED raider band */\n'
        '    LOAD1(0x1, UnitDef_088B4718) /* the 3 GREEN chwinga (protect layer) */\n'
        '    ENUN\n'
        '    FADU(16) /* reveal the battle map */\n'
        '    CALL(EventScr_08591FD8) /* preparations (PREP, event cmd 0x3E) -- cap 5 */\n'
        '    ENUT(8)\n'
        '    EVBIT_T(7)\n'
        '    ENDA\n}' % CH02_HOST_INDEX, CH3_EVENTSCRIPT_H)
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
        % (CH02_ITEM_IDS[gift], uid, slot.upper(), 0x30 + i, 0x30 + i)
        for i, (uid, slot, gift) in enumerate(CH02_CHWINGA))
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
        + dev_placeholder_scene() +     # ch03 not hosted yet -> dev landing, then title
        '    ENDA\n}', CH3_EVENTSCRIPT_H)
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
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n'
    if bq.count(head) != 1:
        sys.exit('ERROR: gDefeatTalkList head not in expected form in %s' % BATTLEQUOTES_C)
    bq = bq.replace(head, head + quote + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)

    # 6. Texts. Overwritten ids are dead vanilla Ch3 scene/talk/turn messages (the vanilla
    #    Ch3 scenes are gone); 0x993/0x994 are LIVE battle quotes and are NOT in the pool.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat all foes'))
    set_message_body(lines, host['goal']['windowTextId'],
                     name_message_body('Rout the enemy'))
    set_message_body(lines, CH02_OPENING_CARD_MSG, name_message_body(op_card))
    for msg_id, beat in zip(CH02_OPENING_MSGS, op_beats):
        w = 28 if _beat_is_narration(beat) else 42
        set_message_body(lines, msg_id, _script_to_message(
            beat, stage(beat, op_home), width=w))
    # Turn-1 fliers-vs-bows tutorial: one portrait box per line (RBG, then Pinky), Text_BG 42-wrap.
    for msg_id, ln in zip(CH02_TUTORIAL_MSGS, tutorial):
        set_message_body(lines, msg_id, _script_to_message(
            [ln], stage([ln], op_home), width=42))
    # Wolfram's rear-ambush bark, shown over the map (29-tile bubble wrap; the 31-char
    # "Wolves at our backs -- the sled." auto-wraps via _wrap_fe_lines).
    set_message_body(lines, CH02_BARK_MSG, _script_to_message(
        bark, {'wolfram': ('[OpenMidLeft]', _fid_tag(PORTRAIT_MAP['wolfram'].upper()))},
        width=29))
    set_message_body(lines, CH02_ENDING_CARD_MSG, name_message_body(end_card))
    for msg_id, beat in zip(CH02_ENDING_MSGS, end_beats):
        w = 28 if _beat_is_narration(beat) else 42
        set_message_body(lines, msg_id, _script_to_message(
            beat, stage(beat, {}), width=w))
    set_message_body(lines, CH02_BOSS_DEATH_MSG, _script_to_message(
        [{'halvar': halvar['death_quote']}],
        {'halvar': ('[OpenMidRight]', _fid_tag(CH02_BOSS_SLOT))}, width=29))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 6a. Title card image (4bpp banner) -- DEFERRED (#22 "Title card" checklist item).
    #     gen_chapter_title's atlas lacks the "Ch.2: Cold Welcome" glyphs (C/W/d/m + the
    #     "Ch.2:" prefix), and composing them means cutting glyphs by eye from the vanilla
    #     cards -- a visual artifact for Nicolas to sign off. Until then the vanilla slot-3
    #     card shows as a placeholder; the build stays green. To finish: extend
    #     LETTERS/WORDS in gen_chapter_title.py, then compose chap_title_<chapTitleId>.png
    #     (cf. inject_ch01 step 6a).

    if verbose:
        print('  ch02 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'DefeatAll, deploy cap %d + PREP (lord auto-force-deployed)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH02_HOST_INDEX, len(deploy)))
        print('  rosters: party persists, %d chardalyn raiders (Grukk@%s Halvar@%s) + %d '
              'rear raiders turn %d; %d GREEN chwinga (per-survivor charm-gifts)'
              % (len(enemies), (gx, gy), (hx, hy), len(reinforce),
                 reinf['trigger_turn'], len(chwinga)))


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
    with open(DATA_TERRAINS_C, 'w', encoding='utf-8') as f:
        f.write(dt)

    # 4. extern (variables.h) + switch case (banim-battleparse.c) for Tileset15
    with open(VARIABLES_H, encoding='utf-8') as f:
        vh = f.read()
    vh = vh.replace('extern CONST_DATA s8 BanimTerrainGround_Tileset01[];',
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset15[];\n'
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset01[];', 1)
    with open(VARIABLES_H, 'w', encoding='utf-8') as f:
        f.write(vh)
    with open(BANIM_BATTLEPARSE_C, encoding='utf-8') as f:
        bp = f.read()
    bp = bp.replace(
        '    case 0:\n    default:\n        return BanimTerrainGroundDefault[terrain];',
        '    case 0x15:\n        return BanimTerrainGround_Tileset15[terrain];\n\n'
        '    case 0:\n    default:\n        return BanimTerrainGroundDefault[terrain];', 1)
    with open(BANIM_BATTLEPARSE_C, 'w', encoding='utf-8') as f:
        f.write(bp)

    # 5. point Ch1 (chapter idx 2) at the rough snow tileset (0x15); prologue (idx 1) keeps 0
    with open(CHAPTER_SETTINGS_JSON_PLAT, encoding='utf-8') as f:
        cs = _json.load(f)
    cs['chapters'][2]['battleTileSet'] = 0x15
    with open(CHAPTER_SETTINGS_JSON_PLAT, 'w', encoding='utf-8') as f:
        _json.dump(cs, f, indent=2)

    if verbose:
        print('  %d platforms -> battle_terrain_table[%d..%d] (FE-Repo {Cynon}, F2E)'
              % (len(BATTLE_PLATFORMS), base, base + len(BATTLE_PLATFORMS) - 1))
        print('  terrain->ground: Default=snow-open (Snowdrift); Tileset15=snow-rough; Ch1->0x15')


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
    args = ap.parse_args()

    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
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
        engine_hooks._inject_lord_select_engine()
        print('  lord select (#42): GetPid + force-deploy/Seize/game-over keyed to the chosen lead')
        engine_hooks._inject_lord_floor_engine()  # after lord-select: anchors on its LordSelect_GetPid
        print('  lord floor (#45 3c): chosen lead\'s survivability top-up baked in once at ch start')
        print('names:')
        inject_names(args.campaign)
        print('item names:')
        inject_item_names(args.campaign)
        print('item icons:')
        inject_item_icons(args.campaign)
        print('characters:')
        patch_character_data(args.campaign)
        print('portrait geometry:')
        patch_portrait_geometry(args.campaign)
        print('map sprites:')
        inject_map_sprites(args.campaign)
        print('enemy class reskins (#21):')
        inject_enemy_class_reskins(args.campaign)  # after map sprites (SMS ids), before ch01
        print('battle anims (#65):')
        inject_battle_anims(args.campaign)
        print('winter tileset:')
        inject_winter_tileset(args.campaign)
        print('battle platforms (#65):')
        inject_battle_platforms(args.campaign)
        print('title theme:')
        inject_title_theme(args.campaign)
        print('title screen:')
        inject_title_screen(args.campaign)
        print('chapter 1 (#21):')
        inject_ch01(args.campaign)  # MUST precede inject_prologue (vanilla goal read)
        inject_northlook_bitey()    # 'Ol Bitey over the tavern hearth (Beat 1 set dressing)
        print('chapter 2 (#22):')
        inject_ch02(args.campaign)  # hosts slot 3; ch01's ending MNC2(0x3) lands here
        if args.test_chapter:
            print('TEST CHAPTER (playtest: New Game -> Ch1 sandbox, cast deployed):')
            inject_test_chapter(args.campaign)   # slot 1 sandbox, in place of the prologue
            _configure_boot(TEST_CHAPTER_INDEX)  # sandbox never montages
        else:
            print('prologue (New Game target):')
            inject_prologue(args.campaign, montage=args.montage)
            _configure_boot(PROLOGUE_HOST_INDEX, montage=args.montage)
        print('death quotes (#6):')
        inject_pc_death_quotes(args.campaign)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
