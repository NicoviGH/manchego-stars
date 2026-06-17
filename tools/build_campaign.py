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
import gen_chapter_title  # noqa: E402
import gen_subtitle_cards  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')
CHARACTERS_C = os.path.join(DECOMP, 'src', 'data_characters.c')
CLASSES_C = os.path.join(DECOMP, 'src', 'data_classes.c')
CLASSES_H = os.path.join(DECOMP, 'include', 'constants', 'classes.h')
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
WORLDMAP_PATH_C = os.path.join(DECOMP, 'src', 'worldmap_path.c')
WORLD_MAP_GFX_DIR = os.path.join(DECOMP, 'graphics', 'world_map')
TOUR_TEXT_ID = 0x8DB   # vanilla's WM narration message, referenced only here
# Map (overworld) sprites (#38). FE8 map sprites are CLASS-driven (GetUnitSMSId ->
# pClassData->SMSId), so two cast on the same class share one sprite and enemies of
# that class would inherit a swap. We instead give each cast member a custom SMS slot
# and a per-CHARACTER override in GetUnitSMSId -- stock classes and vanilla enemies
# untouched. Classes top out at SMSId 106 (verified), so 107+ is free in both the
# wait array (extended here) and the move table (dead tail; no class reaches it).
BMUNIT_C = os.path.join(DECOMP, 'src', 'bmunit.c')
BMMAP_C = os.path.join(DECOMP, 'src', 'bmmap.c')
BMCAMADJUST_C = os.path.join(DECOMP, 'src', 'bmcamadjust.c')
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
BATTLEQUOTES_C = os.path.join(DECOMP, 'src', 'data_battlequotes.c')
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
EVENTINFO_C = os.path.join(DECOMP, 'src', 'eventinfo.c')
BMDIFFICULTY_C = os.path.join(DECOMP, 'src', 'bmdifficulty.c')
LORDSEL_FLAG_BASE = 0xF0
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
CH01_ENDING_MSGS = (0x946, 0x947, 0x948, 0x949, 0x94A, 0x94B)  # AB,C,D,E1,E2,F
CH01_BODY_MSG = 0x956    # the dismembered sled-driver, found just past the road sign
CH01_TAUNT_MSG = 0x960   # Izobai's turn-1 boss taunt (both dead vanilla Ch1-tutorial slots)
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
                        # (data_battlequotes.c) ride files already listed above
                        'src/eventinfo.c', 'src/bmdifficulty.c'] + [
                        'graphics/op_subtitle/OpSubtitle_%02d.png' % i
                        for i in range(gen_subtitle_cards.CARD_COUNT)]


def restore_vanilla_sources():
    subprocess.run(['git', '-C', DECOMP, 'checkout', '--'] + PATCHED_DECOMP_FILES,
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

def _find_brace_block(text, marker, path):
    """Return (start, end) covering the `{...}` (brace-balanced) after `marker`."""
    at = text.find(marker)
    if at < 0:
        sys.exit('ERROR: %r not found in %s' % (marker, path))
    brace = text.find('{', at)
    depth = 0
    i = brace
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return brace, i + 1
        i += 1
    sys.exit('ERROR: unbalanced braces for %r in %s' % (marker, path))


def _set_field(block, field, value, path, marker):
    """Replace `.field = ...,` within `block`. Errors if the field isn't present."""
    pat = re.compile(r'(\.' + field + r'\s*=\s*)[^,\n]*(,)')
    new, n = pat.subn(lambda m: m.group(1) + str(value) + m.group(2), block, count=1)
    if n == 0:
        sys.exit('ERROR: field .%s not found in %s entry %s' % (field, path, marker))
    return new


def class_base_stats(class_enum):
    """Read a class's base stats from data_classes.c, keyed by CharacterData field
    name (baseHP, basePow, ...). Luck is character-only, so baseLck defaults to 0."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
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
    vanilla = text  # snapshot for reading stat-donor growths/ranks (pre-patch)

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
        block = _set_field(block, 'defaultClass', class_enum, CHARACTERS_C, marker)
        block = _set_field(block, 'affinity', 'UNIT_AFFIN_ANIMA', CHARACTERS_C, marker)
        block = _set_field(block, 'baseLevel', int(st.get('level', 1)), CHARACTERS_C, marker)

        deltas = {}
        for fe in st:
            field = STAT_FIELD.get(fe)
            if field is None:
                continue
            delta = int(st[fe]) - cbase.get(field, 0)
            deltas[field] = delta
            block = _set_field(block, field, delta, CHARACTERS_C, marker)

        # Growths + weapon ranks: take a class-matched vanilla unit's (the donor),
        # so the unit levels and fights like a real FE unit of its class.
        donor = STAT_DONOR[unit_id]
        growths, ranks = donor_growths_and_ranks(vanilla, donor)
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
            print('  %-10s -> %-8s: %s L%s  %s  growths+ranks<-%s%s%s'
                  % (unit_id, slot, class_enum, st.get('level', 1), shown,
                     donor.replace('CHARACTER_', ''),
                     '  [F]' if female else '', tag))

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


def _replace_brace_block(text, marker, new_body, path):
    """Replace the `{...}` after `marker` with `new_body` (a `{...}` string)."""
    s, e = _find_brace_block(text, marker, path)
    return text[:s] + new_body + text[e:]


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
            '    },' % (slot.upper(), class_enum, leader,
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
                     '    LOAD1(1, UnitDef_Event_Ch1Ally)\n'
                     '    ENUN\n'
                     '    ENDA\n'
                     '}')
    script = _replace_brace_block(
        script, 'EventScr_Ch1_BeginningScene[] =', minimal_begin, CH1_EVENTSCRIPT_H)
    with open(CH1_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # Dev loop: cut every pre-map sequence so a fresh boot lands on the title and New
    # Game drops straight onto the map, then redirect the prologue slot -> Ch1 so the
    # New Game target is this sandbox chapter.
    _cut_boot_intro()
    _redirect_new_game(TEST_CHAPTER_INDEX)

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
    LORDSEL_FLAG_BASE + menu index. Four campaign-agnostic hooks consume it:
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
    with open(ts_c, 'w', encoding='utf-8') as f:
        f.write(src)
    if verbose:
        print('  boot title -> "MANCHEGO STARS" + "RIME OF THE / FROSTMAIDEN"')


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
        '        .items = { ITEM_SWORD_STEEL },\n'
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
        '}' % sephek_slot)
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
    #    FE8's 12-char buffer -- see [[manchego-stars-fe-name-truncation]]).
    chap = _load_prologue_chapter(campaign)
    by_id = {u['id']: u for u in chap['player_units'] + chap['enemy_units']}
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

    # 6. Boot flow: cut the attract/intro/world-map sequences, and redirect New Game from
    #    the prologue slot (0) to the host chapter (1) at StartBattleMap -- so the game
    #    loads our prologue through the normal-chapter path, dodging the prologue slot's
    #    special-cased HUD/terrain handling that garbled the screen. MONTAGE=1 keeps the
    #    intro monologue and re-renders its slides as our lore crawl (#43).
    _cut_boot_intro(montage=montage)
    _redirect_new_game(PROLOGUE_HOST_INDEX)
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
        [('[OpenFarLeft]', b1_fid('braulo')), ('[OpenLeft]', b1_fid('wolfram'))],   # C: party listens (2)
        [],                                                            # D: Hruna<->Hlin two-shot
        [('[OpenMidRight]', b1_fid('hruna'))],                         # E: Hruna across from RBG
    ]
    # beat B: Pinky peeks out far-left beside his father (RBG speaks from mid-left) --
    # they read fine stacked together as a pair (Nicolas, 2026-06-16: keep, don't split).
    b1_overrides = [None, {'pinky': '[OpenFarLeft]'}, None, None, None]

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
    end_preload = [[], [], [], [], [], []]
    end_overrides = [None, {'hruna': '[OpenMidRight]'},
                     {'meesmickle': '[OpenMidRight]'}, None,
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
        cast.append((unit_id, slot, class_enum,
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

    join = [ally_entry(slot, ce, lv, x, y, ', '.join(CLASS_LOADOUT[ce]),
                       ' /* %s */' % uid)
            for (uid, slot, ce, lv), (x, y) in zip(cast, CH01_JOIN_POSITIONS)]
    deploy = [ally_entry(slot, ce, lv, x, y, '0',
                         ' /* deploy slot %d (cap template, never LOADed) */' % i)
              for i, ((uid, slot, ce, lv), (x, y))
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
         for uid, slot, _, _ in cast] +
        ['    0xFFFF,', '};', ''])
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Event lists (ch2-eventinfo.h). Turn: the west wave on turn 3 (vanilla's own
    #    reinforcement idiom: FACTION_ID_BLUE = appear at the start of the player
    #    phase, act on the following enemy phase -- cf. ch9a). Location: the two
    #    vanilla-Ch1-parity hint houses + Seize on the chief's tile (the Seize macro
    #    raises EVFLAG_WIN -> ending scene). Misc: the road-sign AREA trigger +
    #    CauseGameOverIfLordDies (fires on EVFLAG_GAMEOVER, raised by the UnitKill
    #    hook when the chosen lead falls -- _inject_lord_select_engine, #42).
    sx, sy = chap['objective']['seize_tile']
    houses = [e for e in chap['events'] if e.get('type') == 'house']
    sign = next(e for e in chap['events'] if e.get('trigger') == 'unit_on_tile')
    with open(CH2_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    info = _replace_brace_block(
        info, 'EventListScr_Ch2_Turn[] =',
        '{\n    TURN(0x0, EventScr_Ch2_Turn2Player, 1, 0, FACTION_ID_BLUE)'
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
        '{\n    AREA(EVFLAG_TMP(9), EventScr_Ch2_Talk_EirikaRoss, %d, %d, %d, %d)\n'
        '    CauseGameOverIfLordDies\n    END_MAIN\n}'
        % (sign['tile'][0], sign['tile'][1], sign['tile'][0], sign['tile'][1]),
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
    for i, ((uid, slot, _, _), name) in enumerate(zip(cast, cast_names)):
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
    beat1_text_calls = ''.join(
        '    Text(0x%X) /* %s */\n' % (m, lbl)
        for m, lbl in zip(CH01_BEAT1_MSGS, beat1_labels))
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
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Talk_EirikaRoss[] =',
        '{\n    TEXTSHOW(0x955) /* road sign + gouged warning */\n    TEXTEND\n    REMA\n'
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
    end_text_calls = ''.join(
        '    Text(0x%X) /* %s */\n' % (m, lbl)
        for m, lbl in zip(CH01_ENDING_MSGS,
                          ['A+B -- Duvessa thanks them, commissions them, grants the sled, points west',
                           'C -- Wolfram asks Hruna for the iron to armor the sled',
                           'D -- RBG over-engineers it; names it the Rolling Cheddar',
                           'E1 -- Duvessa points to the axe-beak at the market',
                           'E2 -- Marty wins over Baxby the axe-beak (first recruit)',
                           'F -- "Targos is expecting weather. Better hurry."']))
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
        + dev_placeholder_scene() +
        '    ENDA\n}',
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
        set_message_body(lines, msg_id, _script_to_message(
            beat, end_stage(beat, end_overrides[i]), width=42, preload=end_preload[i]))
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


def main():
    ap = argparse.ArgumentParser(description='Inject campaign content into the decomp build.')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--portraits-only', action='store_true',
                    help='only inject portrait assets (skip names + characters)')
    ap.add_argument('--montage', action='store_true',
                    help='wire the #43 opening montage (lore crawl) instead of the '
                         'dev boot cut; dev builds keep the straight-to-map boot')
    args = ap.parse_args()

    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
    print('portraits:')
    inject_portraits(args.campaign)
    if not args.portraits_only:
        restore_vanilla_sources()  # clean base each build (idempotent; vanilla donor reads)
        print('engine hardening:')
        _patch_player_start_cursor_guard()
        print('  GetPlayerStartCursorPosition: fall back to first player unit if leader undeployed')
        _patch_terrain_name_guard()
        print('  GetTerrainName: bounds-guarded against OOB terrain ids (defensive)')
        _patch_battle_map_kind_fallback()
        print('  GetBattleMapKind: no-world-map fallback = STORY (slot 2+ chapters)')
        _inject_lord_select_engine()
        print('  lord select (#42): GetPid + force-deploy/Seize/game-over keyed to the chosen lead')
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
        print('winter tileset:')
        inject_winter_tileset(args.campaign)
        print('title theme:')
        inject_title_theme(args.campaign)
        print('title screen:')
        inject_title_screen(args.campaign)
        print('chapter 1 (#21):')
        inject_ch01(args.campaign)  # MUST precede inject_prologue (vanilla goal read)
        inject_northlook_bitey()    # 'Ol Bitey over the tavern hearth (Beat 1 set dressing)
        print('prologue (New Game target):')
        inject_prologue(args.campaign, montage=args.montage)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
