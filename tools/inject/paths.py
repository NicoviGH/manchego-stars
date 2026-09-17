#!/usr/bin/env python3
"""Where every decomp file we touch LIVES -- one home for the paths (#389).

These 79 constants were spread through `build_campaign.py`, and every domain in that file
reached for them: the coupling audit found each region referencing 6 to 53 module-level
names, and almost all of them were these. Extracting the paths first is what makes the rest
of the decomposition a series of small, independent moves instead of one 15,000-line
rewrite.

Paths only. Anything that computes, decides or patches belongs in the domain module that
owns the decision -- a path constant is the one kind of fact with no behaviour attached, so
this module can be imported by anything without creating a cycle.

`build_campaign.py` re-exports every name here, so existing call sites are unchanged.
"""
import os

# tools/inject/paths.py -> tools/inject -> tools -> repo root. THREE levels, not two:
# build_campaign.py sits one directory higher, so copying its two-dirname form here pointed
# REPO at tools/ and every decomp path went with it.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECOMP = os.path.join(REPO, 'fireemblem8u')

PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')

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

UIARENA_C = os.path.join(DECOMP, 'src', 'uiarena.c')

CP_DATA_C = os.path.join(DECOMP, 'src', 'cp_data.c')     # the AI script tables + their lists

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

# --- Prologue chapter (#20) -------------------------------------------------------
# The real New Game target: our designed ch00 ("A Dagger of Ice") on a winter map --
# Scramsax (strong Jagen) + frail Hlin vs Sephek (boss, escapes) + 2 guards. Replaces
# the test-chapter spawn as main()'s in-engine entry. Design SoT:
# campaigns/.../chapters/ch00-prologue-a-dagger-of-ice.yaml.
PROLOGUE_UDEFS_H = os.path.join(DECOMP, 'src', 'events', 'prologue-eventudefs.h')

PROLOGUE_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'prologue-eventinfo.h')

PROLOGUE_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'prologue-eventscript.h')

# --- Chapter 1 (#21): "The Iron Trail" ---------------------------------------------
# Hosted on chapter slot 2 (CHAPTER_L_2): ch00's ending hands off with MNC2(0x2), and
# slot-N+1 hosting keeps every campaign chapter on a normal vanilla slot (same dodge
# as the prologue's slot-0 avoidance). Design SoT: chapters/ch01-the-iron-trail.yaml.
CH2_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch2-eventinfo.h')

CH2_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch2-eventscript.h')

CH3_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch3-eventinfo.h')

CH3_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch3-eventscript.h')

EVENTS_UDEFS_C = os.path.join(DECOMP, 'src', 'events_udefs.c')

BUILD_STAMP = os.path.join(REPO, '.build-config.json')

# What each injection step wrote, per scope. Read by tools/playtest/matrix.py to decide
# which scenarios a change can possibly have affected (#255 phase 2). Gitignored for the
# same reason as the build stamp: it describes this tree's build, not the source.
BUILD_SCOPES_PATH = os.path.join(REPO, '.build-scopes.json')

# Where a config-invariant injection step's output is kept between builds (#309). Gitignored
# for the same reason as the two above: it describes builds, not source. `NO_INJECT_CACHE=1`
# turns it off, the way `MX_NO_ROM_CACHE` turns off the matrix's ROM cache.
INJECT_CACHE_DIR = os.path.join(REPO, '.injectcache')

DATA_BANIM_S = os.path.join(DECOMP, 'data', 'data_banim.s')

MAP_GFX_DIR = os.path.join(DECOMP, 'graphics', 'map')

MAP_LAYOUT_DIR = os.path.join(MAP_GFX_DIR, 'layout')

CONST_MAPS_S = os.path.join(DECOMP, 'data', 'const_data_chapter_maps.s')

ASSET_TABLE_S = os.path.join(DECOMP, 'data', 'data_8B363C.s')

CHAPTER_SETTINGS_JSON = os.path.join(DECOMP, 'src', 'data', 'chapter_settings.json')

TRAPDATA_C = os.path.join(DECOMP, 'src', 'events_trapdata.c')

EVENTCALL_H = os.path.join(DECOMP, 'include', 'eventcall.h')

CH4_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch4-eventinfo.h')

CH4_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch4-eventscript.h')

CH5_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch5-eventinfo.h')

CH5_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch5-eventscript.h')

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

# --- Chapter 6 (#26): "The Maer Monster" -------------------------------------------
# Hosted on slot 7, filling `Ch7EventData` (CH06_HOST_INDEX / CH06_EVENT_GROUP:
# inject/hosts.py, which states the slot-vs-symbol offset once for the whole build).
# ch06 is the sharpest case of the THREE different vanilla chapters a hosted chapter
# touches, and they are all different on purpose:
#   * the DONOR (geometry) is Ch13 Ephraim -- the layout was retiled from it (#331);
#   * the BAR (enemy pressure, levels, inventories, AI) is Ch6 -- `parity_reference`,
#     and every enemy row derives its donor unit from it (#334/#335);
#   * the HOST (storage: event lists, scripts, message block, goal donor) is slot 7.
# Nothing below mines Ch7 for CONTENT. Slot 7 supplies storage and nothing else.
CH06_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch7-eventinfo.h')

CH06_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch7-eventscript.h')

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
