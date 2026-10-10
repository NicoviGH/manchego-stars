"""Chapter 5 (#25): its injector and everything only it reads.
"""
import os
import re
import sys

import fe8_talk_font
import portrait_tool
from inject.cast import (
    _bust_dir, _classed_cast, _vendor_mug_to_bust, char_symbol, CLASS_LOADOUT, GUEST_PORTRAIT_MAP,
    load_unit, PORTRAIT_MAP)
from inject.chapter_ids import (
    CH04_MOOSE_MOV_TABLE, CH05_ARENA_FOUND_MSG, CH05_ARENA_RULES_MSG, CH05_ARRIVAL_NO_LUPIN_MSG,
    CH05_ARRIVAL_SLOT, CH05_BASIL_JOIN_NO_LUPIN_MSG, CH05_BASIL_JOIN_SLOT, CH05_BOSS_PID,
    CH05_CHAPTER_YAML, CH05_CLASS_IDS, CH05_ENDING_ARMS, CH05_ENDING_LOST_MSG, CH05_ENDING_MSGS,
    CH05_ERUPTION_MSG, CH05_GOAL_STATUS_MSG, CH05_GOAL_WINDOW_MSG, CH05_ITEM_IDS,
    CH05_MOOSE_CHARGE_SLOT, CH05_MOOSE_PID, CH05_MOOSE_QUIP_MSG, CH05_OPENING_SLOTS,
    CH05_RAVISIN_DEATH_MSG, CH05_RAVISIN_TAUNT_MSG, CH05_SAHNAR_ALONE_SLOT, CH05_SAHNAR_TALK_MSG,
    CH05_SAHNAR_TALK_NO_LUPIN_MSG, CH05_VILLAGE_SLOTS, CH05_VISIT_FACES, PROLOGUE_SEPHEK_SLOT)
from inject.decomp import _replace_brace_block, REPO, vanilla_decomp_text
from inject.chapter_frame import write_event_group
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter
from inject.hosts import CH05_EVENT_GROUP, CH05_HOST_INDEX
from inject.maps import (
    _drawn_block, _inject_tile_changes, _map_changes_tileset, _register_chapter_map,
    _register_tileset, _snowy_metatile_for, TILESET_STEMS)
from inject.messages import assert_message_ids_unique
from inject.paths import (
    CH05_EVENTINFO_H, CH05_EVENTSCRIPT_H, CH5_EVENTSCRIPT_H, CP_DATA_C, PORTRAIT_DIR,
    TEXTS_TXT)
from inject.event_scripts import assert_event_scripts_defined, declare_event_script
from inject.recruit import (
    assert_custom_art_pid_wired, on_map_talk_recruits, parley_recruiters, talk_recruit_wiring)
from inject.scenes import (
    _make_fid, _prepend_battle_quote, _prepend_defeat_quote, _split_event_beats, _stage_beat,
    _write_chapter_title_card, battle_quote_pair, boss_quote_message, branch_on_check_alive,
    defeat_quote_row, split_on_stage_cut, variant_beat)
from inject.terrain import (
    _class_terrain_move_costs, _map_terrain_grid, assert_scripted_move_reachable, reachable_tiles,
    reda_route_move)
from inject.text import (
    _fe_dialogue_text, _fid_tag, _script_box_count, _script_to_message, dev_placeholder_scene,
    goal_window_body, name_message_body, SCRIPT_DIRECTIVES, set_message_body)
from inject.units import (
    _ally_unit_entry, _deploy_cap_entries, _enemy_unit_entry,
    _items_with_drop_last, chapter_label_constant, declare_unit_table,
    enemy_ai_initialiser, safe_ai_clients)
from inject.villages import (
    assert_village_gifts_match_vanilla, assert_village_tiles_visitable, DEFAULT_VILLAGE_SPEAKER,
    location_events, save_all_bonus_script, village_boxes, village_reward_item, village_script)


# The portrait podiums in SCREEN order, left to right (tag codes in tools/textencode/msg_list.txt:
# FarFarLeft 14, FarLeft 8, MidLeft 9, Left 10, Right 11, MidRight 12, FarRight 13, FarFarRight 15
# -- the numbering is not the layout, which is exactly why this is written down).
PODIUM_ORDER = ('[OpenFarFarLeft]', '[OpenFarLeft]', '[OpenMidLeft]', '[OpenLeft]',
                '[OpenRight]', '[OpenMidRight]', '[OpenFarRight]', '[OpenFarFarRight]')


def assert_silent_faces_have_elbow_room(script, podiums, where):
    """A `present:` face must not sit on a rung next to one that speaks.

    Adjacent podiums overlap: the portraits are wider than the gap between neighbouring rungs,
    and FE8 draws the active speaker's face ON TOP of its neighbour's. For a scene of speakers
    that is harmless and vanilla does it constantly -- ch05's own scene 4 seats four across
    FarLeft/MidLeft/MidRight/FarRight, and each of the four is drawn over the others when its
    turn comes, so everyone is legible in motion.

    A `present:` face never gets that turn. It is underneath for the whole scene. Found by
    filming, not by reading (#25, 2026-08-14): scene 3 seated Ravisin on MidRight and the raised
    Sahnar on FarRight, and Sahnar spent the scene as a hood behind Ravisin's shoulder -- every
    id, count and wrap correct, and the beat invisible. This is the assertion that scene could
    not have had before, because silent faces did not exist before it.

    Vanilla's stable two-face right side leaves a rung EMPTY between the pair -- Right +
    FarRight, never MidRight + FarRight (MSG_904, MSG_092C, MSG_0937, MSG_0954), reached in
    three of those four by loading on an inner rung and sliding out with `[MoveRight]`.

    Unknown tags are ignored rather than rejected, so a faceless narration seat or a future tag
    cannot fail a build on a guess.
    """
    silent = {text for entry in script for k, text in entry.items() if k == 'present'}
    for name in sorted(silent):
        seat = podiums.get(name)
        if seat not in PODIUM_ORDER:
            continue
        for other, tag in sorted(podiums.items()):
            if other == name or tag not in PODIUM_ORDER:
                continue
            # 0 as well as 1: SHARING a podium is the worse version of the same fault -- the
            # renderer evicts the silent face with [ClearFace] the moment its holder speaks, so
            # it is destroyed before the first box rather than merely buried. Easy to hit,
            # because the shared podium tables pair names onto tags (ch05's basil/sephek and
            # sahnar/ravisin both collide), which is exactly how this scene started out.
            if abs(PODIUM_ORDER.index(tag) - PODIUM_ORDER.index(seat)) <= 1:
                sys.exit('ERROR: %s stages %s silently on %s, which %s %s -- the portraits '
                         'overlap and the SPEAKER wins, so a face that never takes a turn is '
                         'buried (adjacent) or cleared outright (same podium). Leave a rung '
                         'empty between them, as vanilla does (Right + FarRight, never MidRight '
                         '+ FarRight).'
                         % (where, name, seat,
                            'also holds' if tag == seat else 'sits next door to on',
                            other if tag == seat else tag))


def _script_staged_names(script):
    """Every character a script puts on screen -- speakers AND silent `enters`/`exits` targets.

    A speaker set read off the keys alone misses anyone who only ever ARRIVES or LEAVES, and
    those still need a podium: `_script_to_message` looks them up in `staging` exactly as it
    looks up a speaker. Sahnar in ch05's scene 3 is the founding case -- she is raised on
    screen and never says a word.
    """
    names = {k for entry in script for k in entry if k not in SCRIPT_DIRECTIVES}
    names |= {text for entry in script for k, text in entry.items()
              if k in ('present', 'exits')}
    return names


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


def _chapter_event_by_slot(chap, trigger, slot, err_label):
    """The one chapter event with `trigger` AND the `slot:` anatomy label `slot`.

    ch03/ch04 author their opening as ONE `chapter_start` event split on `beat_break`, so
    `_split_event_beats` can find it by trigger alone. ch05 authors each scene as its own
    `chapter_start` event, labelled by the vanilla scene it mines -- seven of them -- and a
    lookup by trigger silently returns the first. Match on both.
    """
    hits = [e for e in chap['events']
            if e.get('trigger') == trigger and e.get('slot') == slot]
    if len(hits) != 1:
        sys.exit('ERROR: %s: expected exactly one %r event labelled %r, found %d'
                 % (err_label, trigger, slot, len(hits)))
    return hits[0]


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


CH05_BEGINNING_SCRIPT = 'EventScr_Ch6_BeginningScene'
CH05_ENDING_SCRIPT = 'EventScr_Ch6_EndingScene'
# Dead host-slot scripts repurposed for our reinforcement waves. Unreachable once the event
# lists above are stripped; each verified free by grep (the ch03/ch04 idiom).
CH05_WAVE_SCRIPTS = {2: 'EventScr_089F2B74', 6: 'EventScr_089F2940', 8: 'EventScr_089F2A98'}
CH05_PREP_SCRIPT = 'EventScr_08591FD8'           # the shared CLEAN/PREP/CLEAN script (cf. ch03/ch04)

# Our OWN roster tables (declare_unit_table). Named for the chapter whose units are in them.
CH05_ALLY_TABLE = 'MS_Ch05DeployCap'             # the never-LOADed PREP cap template
CH05_BOOT_SEED_TABLE = 'MS_Ch05BootSeed'         # --ch05-boot only: an armed party from a cold start
CH05_LUPIN_PROOF_TABLE = 'MS_Ch05LupinProof'     # --ch05-lupin only: Lupin, LOADed before the
                                                 # opening's CHECK_ALIVE so the ALIVE arm is
                                                 # reachable from a cold boot (see inject_ch05)
CH05_LINE_TABLE = 'MS_Ch05Line'                  # the 16 turn-1 tomb-guardians
CH05_SAHNAR_TABLE = 'MS_Ch05Sahnar'              # the convertible, on the arena from turn 1
CH05_BASIL_TABLE = 'MS_Ch05Basil'                # Basil, GREEN at the pocket mouth (see below)
CH05_WAVE_TABLES = {2: 'MS_Ch05Wave2', 6: 'MS_Ch05Wave6', 8: 'MS_Ch05Wave8'}

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
# The join beat SPEAKS, at CH05_BASIL_JOIN_SLOT's 0x9EE (and 0x9EF on the no-Lupin arm) -- ids
# from ch05's OWN block, which is the point this comment exists to make. ch05's YAML labels its
# scenes `slot: "vanilla 0x9C2"` and the like, but those labels are ANATOMY REFERENCES to the
# chapter we MINE (vanilla Ch5) -- they are not ids we may write, because ch04 hosts on slot 5 and
# owns that whole block (HOSTED_CHAPTER_MESSAGE_IDS['ch04'] = 0x9BA..0x9C6). 0x9C2 in the built
# ROM is ch04's OWN no-parley ending (CH04_ENDING_NO_LUPIN_MSG), so pointing Basil's join at it
# would have played Pinky and Marty discussing supper. Reading an UNWRITTEN vanilla id as a
# placeholder is fine and we do it (the reliquary visits, and the Talk below); reading one another
# chapter WRITES is not -- that distinction is the whole reason the registry exists.
CH05_SAHNAR_TALK_SCRIPT = 'MS_Ch05SahnarTalk'   # ours (declare_event_script), not a squatted
CH05_SAHNAR_TALK_FLAG = 'EVFLAG_TMP(7)'   # vanilla Ch5's own Natasha->Joshua CHAR flag, free
                                          # here: ch05's villages use 9..12, and Misc uses 13
                                          # for the arena tutorial.
CH05_ARENA_TUTORIAL_FLAG = 'EVFLAG_TMP(13)'  # 7 Talk; 8 prep; 9..12 reliquaries; next free
CH05_ARENA_TRIGGER_SCRIPT = 'MS_Ch05ArenaTutorialTrigger'
CH05_ARENA_TUTORIAL_SCRIPT = 'MS_Ch05ArenaTutorial'
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
# The elven store (`economy.elven_store`). Armory/Vendor take their stock DIRECTLY -- no script,
# no text -- so these are wired PERMANENTLY, not as placeholders. Stock is vanilla Ch5's own,
# which is what `make difficulty CH=ch05` prices the shop tier against.
CH05_SHOPS = (('Armory', 'ShopList_Event_Ch5Armory', 2, 1),
              ('Vendor', 'ShopList_Event_Ch5Vendor', 6, 10))

CH05_LAYOUT = ('Ch05ElvenTombMap', 'ch05-the-elven-tomb')   # (asset label, maps/ stem)
CH05_TILESET = 'port-or-town-winter'             # stem 'PortTown'; ch05 is the first chapter to
                                                 # use it, so it self-registers (the Cave idiom)
CH05_GOAL_DONOR = 7                              # vanilla slot 7 = a clean defeat_boss template.
# ── The opening's BACKDROP half (#25): three scenes at the tomb, before the party arrives ──
# CHANNEL is not a preference here, it is inherited. Vanilla Ch5's own BeginningScene plays its
# first four messages over a BACKDROP and only then moves onto the map:
#   0x9BA Text_BG(SERAFEW) | 0x9BB SetBackground(SERAFEW)+TEXTSHOW | 0x9BC/0x9BD Text_BG(SERAFEW)
#   | 0x9BE SetBackground(TOWN)+TEXTSHOW | 0x9C0..0x9C2 TEXTSTART (on-map) | PREP | 0x9C3/0x9C4.
# `vanilla_scene.py` prints 0x9BB as "map" because it is a bare TEXTSHOW; the SetBackground two
# lines above it is what it actually plays over. So the Joshua/Natasha meet-cute -- our scene 1's
# twin -- is a BACKDROP scene, and our three tomb scenes are too. It also settles the question the
# scene table left open: nothing is staged on the field this early, so no talk bubble has a unit
# to anchor to (PutTalkBubble needs one); both windows now take one measured pixel budget.
#
# ONE backdrop across all three, which is vanilla's habit too -- it spends BG_SERAFEW_VILLAGE on
# four consecutive scenes and only switches to BG_TOWN when the party physically arrives.
CH05_OPENING_BG = 'BG_MS_ELVEN_TOMB'
# ── Scene 4 (#25): the party CRESTS THE RIDGE -- and the chapter's first BRANCH ──────────────
# Still the opening's backdrop half, but it cuts to a second BG, and that cut is inherited too:
# vanilla Ch5 spends BG_SERAFEW_VILLAGE on four consecutive scenes and switches to BG_TOWN at
# exactly this beat, when its travellers physically arrive. The first three scenes are the tomb
# seen from inside; this one is the party standing on the ridge above it.
CH05_ARRIVAL_BG = 'BG_MS_FOREST_OUTSKIRTS_WINTER'
# Lupin's MAP identity, which is his PORTRAIT_MAP slot -- NOT his STAT_DONOR (Kyle is a stat
# reference and nothing else, and CHECK_ALIVE resolves a pid through GetUnitFromCharId).
CH05_LUPIN_CHARACTER = char_symbol(PORTRAIT_MAP['lupin'])
# One speaker, and she keeps the mid-left she holds in the Talk recruit and in the tomb scenes --
# a character who changes seats between her scenes reads as a different person each time.
CH05_BASIL_JOIN_PODIUMS = {'basil': '[OpenMidLeft]'}
# Both branches live in ONE event list, and BEQ/GOTO scan that list for a matching LABEL -- so the
# join's arms must not be numbered 0/1 like the arrival's, or a jump lands in the wrong scene.
CH05_BASIL_JOIN_LABEL_BASE = 2
# She keeps the mid-right she holds in scene 1 and in the Talk recruit -- and it is the podium
# vanilla's own 0x9C3 gives Joshua, alone on this same tile. NO no_lupin_fallback: she has never
# met the wolf and does not mention him, so this scene has one arm and costs one id.
CH05_SAHNAR_ALONE_PODIUMS = {'sahnar': '[OpenMidRight]'}
# Pinky KEEPS THE FAR RIGHT he holds in scene 4 -- he closes the arrival on either arm and he
# opens this one, and a character who changes seats between his scenes reads as a different
# person each time. Meesmickle has no ch05 seat yet and takes mid-left: the widest two-shot the
# ladder offers against FarRight, so the setup and the punchline come from opposite sides of the
# screen rather than from neighbouring rungs.
CH05_MOOSE_CHARGE_PODIUMS = {'meesmickle': '[OpenMidLeft]', 'pinky': '[OpenFarRight]'}
# The bellow itself, and it is a BACKGROUND rather than a portrait for one reason: a 96x80 bust
# is drawn inside the talk window's envelope and this animal's antlers do not fit it. A BACG owns
# the whole 240x160 screen and has no envelope, which makes "show the creature properly" a
# solved problem rather than a compromise (Nicolas's art + Nicolas's idea, 2026-08-15).
CH05_MOOSE_BELLOW_BG = 'BG_MS_WHITE_MOOSE'
# The first sound effect this project has ever AUTHORED -- every other note in the game is
# vanilla's, played through the music commands vanilla itself uses, and `SOUN` had never been
# called (Nicolas, 2026-08-15). Vanilla also names almost none of its ~340 sound effects, so a
# cry has to be found by id -- and WHICH ID SPACE is the whole story here. `banim_code_sound_*`
# in banim_code.inc encodes 0x850000XX, and XX is NOT a song id -- read as one it yields
# `se_sys_hp2` (an HP-bar tick), `se_sys_bikkuri_mark1` (the "!" popup) and `dummy_song`, all of
# which were auditioned in-engine as monster roars before the mistake surfaced. SONG IDS COME
# FROM sound/song_table.s AND NOWHERE ELSE.
# 0x32C is `song812_mon_mdg_critical1`, the beast critical, chosen by ear by Nicolas off
# tools/sfx_preview.py's audition page -- "the most moosy". Runner-up material lives in the same
# page: the dragon screams (0x0DE, 0x0E6, 0x2F5), the Demon King (0x37A/B, 0x37E) and
# `btl_mon_call1` (0x3BF). Re-pick with `tools/sfx_preview.py --grep <word> --html <file>`;
# it needs no ROM and no emulator.
CH05_MOOSE_BELLOW_SFX = '0x32C'
# Four speakers, four podiums, which is the face budget exactly (FACE_SLOT_COUNT = 4) -- so
# nothing is evicted mid-scene. Seated in the order they speak, left to right, and Pinky holds
# the far right in BOTH arms: he closes the scene on either path, and on the no-Lupin path he
# also opens it.
CH05_ARRIVAL_PODIUMS = {'lupin':   '[OpenFarLeft]',  'wolfram': '[OpenMidLeft]',
                        'marty':   '[OpenMidRight]', 'pinky':   '[OpenFarRight]'}
# Podiums, held ACROSS the three scenes rather than chosen per scene: Basil and Sephek on the
# party/left side, the two who outrank them on the right. Ravisin speaks in both scene 2 and
# scene 3 and holds the same podium in each, so she does not appear to change seats between a
# scene and its immediate sequel. Basil likewise keeps the mid-left she holds in the Talk recruit.
CH05_OPENING_PODIUMS = {'basil': '[OpenMidLeft]',  'sahnar':  '[OpenMidRight]',
                        'sephek': '[OpenMidLeft]', 'ravisin': '[OpenMidRight]'}
# Per-scene seat changes, for the one case where the shared table cannot hold: scene 3 puts
# SAHNAR on screen while Ravisin is talking, so the right side has to hold TWO faces.
#
# ADJACENT RUNGS COLLIDE -- USE EVERY OTHER ONE. The podium tags are a ladder
# (msg_list.txt: Right 11, MidRight 12, FarRight 13), and two faces on NEIGHBOURING rungs
# overlap: filmed 2026-08-14 with Ravisin on MidRight and Sahnar on FarRight, Sahnar drew as a
# sliver behind her and then vanished outright the moment Ravisin took the next box. Vanilla
# never pairs neighbours. Its stable two-face right side is always **Right + FarRight**, with
# MidRight deliberately EMPTY between them -- MSG_904 (Eirika/Seth), MSG_092C (Tana/soldier),
# MSG_0937 and MSG_0954 (Eirika + Vanessa + Innes) all land there, the first three by loading on
# an inner rung and then sliding out with an explicit `[MoveRight]`/`[MoveFarRight]`.
#
# So Ravisin moves to `[OpenRight]` for this scene and Sahnar takes `[OpenFarRight]` -- MSG_0954's
# exact MidLeft + Right + FarRight trio, which is also our Basil + Ravisin + Sahnar. Her apparent
# shift from scene 2's mid-right costs nothing: the two scenes are separate messages with a full
# FADI/FADU through black between them, so there is no on-screen seat change to read. (Vanilla's
# `[MoveRight]` would be the other route -- an actual slide as Sahnar comes up, which would sell
# the arrival -- but it needs a Move vocabulary the renderer does not have, and across a fade the
# static reseat is identical on screen.)
CH05_OPENING_PODIUM_OVERRIDES = {
    'vanilla 0x9BD': {'ravisin': '[OpenRight]', 'sahnar': '[OpenFarRight]'},
}
# ── Scenes 16 and 17 (#25): the two ENDINGS ──────────────────────────────────────────────────
# Vanilla's own `EventScr_Ch5_EndingScene` is the twin, and its CHANNEL is inherited like every
# other ch05 scene's (decisions.md -> "A cutscene's CHANNEL is inherited from the twin"): FADI
# takes the map down, `SetBackground` puts a still up, and the text is a full-screen window at
# ~42. Not on-map -- the anatomy table in the ch05 YAML carried "on-map" for these three until
# 2026-08-19 and it was a `vanilla_scene.py` reporting artifact, now fixed and pinned.
#
# It is also the only channel that WORKS here, which is the same argument ch04's ending already
# made for itself: a bubble anchors to a speaking UNIT (PutTalkBubble), these two scenes have
# six speakers between them, and ch05 deploys 9 of a 10-unit pool -- so on-map, half the cast
# could be talking from a tile nobody is standing on. Over a backdrop there is no anchor to want.
CH05_ENDING_BG = 'BG_MS_ELVEN_TOMB'   # back to the tomb face the chapter opened on, which is
# Two branches in one event list, so two label pairs -- and they start at 4 because
# `save_all_bonus_script` (inject.villages) already owns SAVE_ALL_SKIP_LABEL (0x2) further down the same script.
CH05_ENDING_BASIL_LABEL_BASE = 4           # Basil alive -> scene 16, else scene 17
CH05_ENDING_SAHNAR_LABEL_BASE = 6          # inside 16: the full scene, or the cut one
# BASIL holds mid-right for the whole scene and everyone else rotates through mid-left. She
# speaks in every stretch of it, and a rotating anchor would fade the scene's own subject out
# and back in; the others share ONE podium on purpose -- that is the rotating spotlight
# `_script_to_message`'s podium manager exists for, and it keeps the live face count at two.
#
# SAHNAR IS ON THE LEFT WITH THEM, in Wolfram's seat (Nicolas, watching the first film
# 2026-08-19). She was on the far right beside Basil, on the reasoning that the two tomb-dwellers
# belong together against the party -- and on screen that is simply wrong, because the berry
# exchange is a TWO-HANDER: two right-hand podiums put her and Basil shoulder to shoulder both
# facing the same way instead of facing each other.
CH05_ENDING_PODIUMS = {'marty':   '[OpenMidLeft]', 'wolfram':  '[OpenMidLeft]',
                       'braulo':  '[OpenMidLeft]', 'prof-rbg': '[OpenMidLeft]',
                       'sahnar':  '[OpenMidLeft]',
                       'basil':   '[OpenMidRight]'}
CH05_SAHNAR_PID = '0xba'                         # Sahnar: her own pid so Basil's Talk can address
                                                 # HER and not the nearest identical myrmidon
                                                 # (#203's lesson). Becomes her CHARACTER_ slot
                                                 # when the recruit pass gives her one (#25).
CH05_GENERIC_PID = '0x80'                        # autolevelled trash (vanilla Ch6's own generic)


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


def locked_and_variant(script, fallback, render, err_label, msgs):
    """A branched scene as its TWO rendered bodies: the locked one and its substituted twin.

    The pairing every fallback in this campaign takes, kept independent of the CHANNEL because
    the two channels do not render alike -- a backdrop scene goes through `_ch05_opening_body`
    (podium-checked) while an on-map one goes straight to `_script_to_message`. `render` is
    whatever turns a beat into a body; everything else is the part that must not be written
    twice.

    Whole copies rather than a prefix/arm/suffix split, which is vanilla's own economy: ch14a's
    ending branches to `TEXTSHOW(0xa93)` or `TEXTSHOW(0xa95)`, two complete messages, and shares
    the script around them. Duplicated text is free; seams in a scene are not.
    """
    locked_msg, variant_msg = msgs
    return [(locked_msg, render(script)),
            (variant_msg, render(variant_beat(script, fallback, err_label)))]


CH05_ENDING_SLOT = 'vanilla 0x9C9'          # scene 16 -- Basil alive
CH05_ENDING_LOST_SLOT = 'vanilla 0x9CA'     # scene 17 -- Basil died


def _ch05_ending_variants(chap, slot, boxes, what):
    """One locked ending scene as its arms: {sahnar_recruited: script}.

    Each arm is the WHOLE scene, generated from the one locked script -- scene 16's shorter one
    by `variant_beat` applying the `no_sahnar_cut:`, whose `replaces:` anchors assert the drop
    lands where the YAML says. Nothing is hand-duplicated, so there is no second copy of the
    prose to drift.

    Scene 17 declares no cut (Sahnar is silent over the body whether or not she was recruited)
    and comes back with one arm.
    """
    event = _chapter_event_by_slot(chap, 'chapter_end', slot, 'ch05 ending (%s)' % what)
    script = event['script']
    if _script_box_count(script) != boxes:
        sys.exit('ERROR: ch05 ending %r (%s) must remain the %d locked boxes; got %d'
                 % (slot, what, boxes, _script_box_count(script)))
    # Neither ending branches on Lupin any more, and a fallback that came back would be wired
    # silently by nothing -- so refuse it here rather than let it sit in the YAML looking live.
    # Why it went: "like she woke the wolves" was read as naming an optional RECRUIT, and ch04
    # fights the pack on every path. See CH05_ENDING_MSGS.
    if 'no_lupin_fallback' in event:
        sys.exit('ERROR: ch05 ending %r (%s) carries a no_lupin_fallback, and the endings do '
                 'not branch on Lupin -- recruitment decides whether he JOINS, not whether the '
                 'party met the pack, so the locked line is true either way (2026-08-19). '
                 'Nothing reads this block; delete it or re-wire the branch deliberately.'
                 % (slot, what))
    cut = event.get('no_sahnar_cut')
    out = {True: script}
    if cut:
        out[False] = variant_beat(script, cut, 'ch05 ending (%s) no-Sahnar cut' % what)
    return out


def ch05_ending_messages(chap):
    """Both ending scenes as (msg_id, body), at the talk bubble's pixel budget.

    Two bodies for scene 16 -- Sahnar recruited or not -- and one for scene 17, which has no
    berry exchange to lose and nothing else to branch on. Each is ONE continuous message, so
    the podium manager runs the whole scene and Basil never leaves the screen (see
    CH05_ENDING_MSGS).
    """
    out = []
    fid = _make_fid({}, 'ch05 unknown ending speaker')
    arms = _ch05_ending_variants(chap, CH05_ENDING_SLOT, 19, 'Basil alive')
    if set(arms) != set(CH05_ENDING_MSGS):
        sys.exit('ERROR: ch05 ending (Basil alive) produced arms %s but ids are declared for '
                 '%s' % (sorted(arms), sorted(CH05_ENDING_MSGS)))
    # The CUT has to actually shorten the scene, and the ANCHORS cannot prove that on their own:
    # they assert where each named box sits, not that six of them left. A `no_sahnar_cut:` whose
    # `script:` key came back by accident would substitute instead of drop, pass every anchor,
    # and ship a scene that mentions Sahnar to a player who never met her.
    if _script_box_count(arms[False]) != _script_box_count(arms[True]) - 6:
        sys.exit('ERROR: ch05 ending: the no-Sahnar arm is %d boxes against the locked %d -- '
                 'the cut must DROP its six boxes, not replace them'
                 % (_script_box_count(arms[False]), _script_box_count(arms[True])))
    if any('sahnar' in entry for entry in arms[False]):
        sys.exit('ERROR: ch05 ending: the no-Sahnar arm still gives Sahnar a line')
    for recruited, msg in sorted(CH05_ENDING_MSGS.items(), reverse=True):
        beat = arms[recruited]
        out.append((msg, _script_to_message(
            beat, _stage_beat(beat, fid, CH05_ENDING_PODIUMS))))
    lost = _ch05_ending_variants(chap, CH05_ENDING_LOST_SLOT, 10, 'Basil died')[True]
    out.append((CH05_ENDING_LOST_MSG, _script_to_message(
        lost, _stage_beat(lost, fid, CH05_ENDING_PODIUMS))))
    return out


def ch05_ending_script(chap, basil_char, sahnar_char):
    """ch05's ending: the two locked scenes, the save-all payout, then the win.

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
    flag nothing could set -- an unobtainable reward, with a green build.

    The SCENES are ch03/ch04's ending shape (FADI the map out, BACG, FADU, the beat calls,
    FADI into the landing) with vanilla Ch5's own branches inside it, and both come from the
    twin rather than from a preference:

      * the VICTORY STING is picked per arm, not played up front. Vanilla puts `MUSC` inside
        each side of its `CHECK_ALIVE(CHARACTER_NATASHA)` -- SONG_VICTORY when the escort
        lived, SONG_INTO_THE_SHADOW_OF_VICTORY when she did not -- and that is the one place
        ch05 departs from our other four endings, which have nothing to pick between.
      * `CHECK_ALIVE`, never a flag or a field test. It reads the ROSTER, so it survives
        ch05's 9-of-10 deploy, and it collapses never-recruited with recruited-then-killed
        into one arm, which is what all three of these questions want (see
        branch_on_check_alive). Basil is asked first because she is the scene; Sahnar gates
        beat B; Lupin picks beat C's last-but-four box on either side.

    The payout stays after the scenes and BEFORE the FADI for the reason above -- and it is now
    the backdrop that keeps the screen up rather than `EventScr_RemoveBGIfNeeded`, which is
    where vanilla puts its own give too: after the ending text, with something still drawn."""
    flags = {v['id']: CH05_VILLAGE_FLAGS[v['id']] for v in chap.get('villages', [])}
    a, b = CH05_ENDING_SAHNAR_LABEL_BASE, CH05_ENDING_SAHNAR_LABEL_BASE + 1
    alive = ('    MUSC(SONG_VICTORY)\n'
             '    CHECK_EVENTID(%s)\n'
             '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* never turned her -> she never collects it */\n'
             '    CHECK_ALIVE(%s)\n'
             '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* turned her, then lost her -> same silence */\n'
             % (CH05_SAHNAR_TALK_FLAG, a, sahnar_char, a)
             + '    Text(0x%X) /* 16 -- the repotting, the berry, and the Bremen hook */\n'
             % CH05_ENDING_MSGS[True]
             + '    GOTO(0x%X)\n'
               'LABEL(0x%X)\n' % (b, a)
             + '    Text(0x%X) /* 16 -- the same scene, six boxes shorter: nobody to give the '
               'berry to */\n' % CH05_ENDING_MSGS[False]
             + 'LABEL(0x%X)\n' % b)
    lost = ('    MUSC(SONG_INTO_THE_SHADOW_OF_VICTORY)\n'
            '    Text(0x%X) /* 17 -- Basil fell: the facts arrive in fragments and stop */\n'
            % CH05_ENDING_LOST_MSG)
    return ('{\n'
            '    FADI(16) /* fade the hollow out */\n'
            '    REMOVEPORTRAITS\n'
            '    BACG(%s) /* the tomb face, the backdrop the chapter opened on */\n'
            '    FADU(16)\n' % CH05_ENDING_BG
            + branch_on_check_alive(basil_char, alive, lost,
                                    label_base=CH05_ENDING_BASIL_LABEL_BASE)
            + save_all_bonus_script(flags, CH05_ITEM_IDS[chap['economy']['save_all_bonus']])
            + '    FADI(16) /* fade the tomb out into the dev-placeholder landing */\n'
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
    tileset = _map_changes_tileset(maps_dir, CH05_LAYOUT)
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
    """ch05's Location list: the four reliquaries and the elven store."""
    return location_events(chap.get('villages', []),
                           {vid: slot[0] for vid, slot in CH05_VILLAGE_SLOTS.items()},
                           CH05_SHOPS, flags=CH05_VILLAGE_FLAGS)


def ch05_misc_events():
    """ch05's automatic win/lose checks plus the one-shot arena tutorial AREA.

    Vanilla places AREA rows in Misc, whose post-action scan evaluates them against the active
    unit. Location is reserved for commands such as Village, Armory, and Vendor.
    """
    return ('{\n'
            '    DefeatBoss(%s)\n'
            '    AREA(%s, %s, 12, 6, 12, 6) /* one-shot arena tutorial (#264) */\n'
            '    CauseGameOverIfLordDies\n'
            '    END_MAIN\n}'
            % (CH05_ENDING_SCRIPT, CH05_ARENA_TUTORIAL_FLAG,
               CH05_ARENA_TRIGGER_SCRIPT))


def ch05_arena_trigger_script():
    """Player-only AREA target for the arena tutorial. Vanilla's anatomy MINUS its
    tutorial-mode gate (#303).

    Vanilla wraps this in `EventScr_CallOnTutorialMode`, and `CHECK_TUTORIAL` is
    `!config.controller && !(chapterStateBits & PLAY_FLAG_HARD)` (eventscr.c:834) -- true
    only for difficulty menu option 0. So in vanilla the arena tutorial never plays on
    Normal or Difficult.

    We drop that one gate because of what the two boxes SAY: a loss means the unit "will
    not be able to fight in any future battles", and B concedes for the fee. That is a
    permadeath warning plus its escape hatch -- safety text, not a flavour beat -- and a
    Normal player who never sees it can lose a unit to a mechanic nobody explained. Every
    other teaching beat we ship is plain dialogue and already played in all three modes
    (ch02's fliers-vs-bows warning), so this makes the arena consistent with them rather
    than exceptional (Nicolas, 2026-08-22: these, not the rest of tutorial mode).

    The FACTION gate stays: the tile fires for a player unit only. The one-shot flag stays
    too, so it still plays exactly once per run."""
    # Vanilla's helper is just `CHECK_TUTORIAL / BEQ(end) / CALL(-1)` -- the gate plus an
    # indirect call through EVT_SLOT_2 (events_script_utils.c:24). Dropping the gate means
    # the slot hand-off has no purpose either, so this CALLs the script directly, which is
    # the ordinary idiom (cf. ch5-eventscript.h's own `CALL(EventScr_RemoveBGIfNeeded)`).
    return ('{\n'
            '    SVAL(EVT_SLOT_2, FACTION_ID_BLUE)\n'
            '    CALL(EventScr_UnTriggerIfNotFaction)\n'
            '    CALL(%s)\n'
            '    EVBIT_T(7)\n'
            '    ENDA\n}' % CH05_ARENA_TUTORIAL_SCRIPT)


def ch05_arena_tutorial_script():
    """Vanilla EventScr_089F23B4 anatomy, pointed at ch05-owned message ids."""
    return ('{\n'
            '    TUTORIALTEXTBOXSTART\n'
            '    SVAL(EVT_SLOT_B, 0xffffffff)\n'
            '    TEXTSHOW(0x%X)\n'
            '    TEXTEND\n'
            '    REMA\n'
            '    CAMERA(12, 6)\n'
            '    CURSOR_FLASHING(12, 6)\n'
            '    STAL(60)\n'
            '    TUTORIALTEXTBOXSTART\n'
            '    SVAL(EVT_SLOT_B, 0x28ffff)\n'
            '    TEXTSHOW(0x%X)\n'
            '    TEXTEND\n'
            '    REMA\n'
            '    ENUT(234)\n'
            '    CURE\n'
            '    ENDA\n}' % (CH05_ARENA_FOUND_MSG, CH05_ARENA_RULES_MSG))


def ch05_arena_onboarding_wiring(chap):
    """One contract for every output that makes the active arena-wager claim executable.

    Keeping the Misc row, both scripts, and both messages in one value means ``inject_ch05``
    cannot grow a declaration that is never placed or text that is never reached. The onboarding
    guard exercises these generated bodies, then pins the three injection call sites that consume
    them.
    """
    found, rules = ch05_arena_messages(chap)
    return {
        'misc': ch05_misc_events(),
        'scripts': [
            (CH05_ARENA_TUTORIAL_SCRIPT, ch05_arena_tutorial_script(),
             'ch05 arena tutorial -- vanilla 0x9D5/0x9D6 anatomy on host-owned ids (#264)'),
            (CH05_ARENA_TRIGGER_SCRIPT, ch05_arena_trigger_script(),
             'ch05 arena tile trigger -- one-shot AREA, tutorial-mode gated (#264)'),
        ],
        'messages': [
            (CH05_ARENA_FOUND_MSG, found),
            (CH05_ARENA_RULES_MSG, rules),
        ],
    }


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


#  The character id AI_A_07 refuses to attack, and the vanilla list it lives in. Vanilla names
#  the constant for its one and only occupant; ours is the same shape with our escort in it.
ESCORT_SAFE_AI_LIST = 'gUnknown_085A8A00'
ESCORT_SAFE_AI_INDEX = 0x7          # gAi1ScriptTable[AI_A_07] = gAiScript_ActionInRange_ExceptNatasha


def repoint_escort_safe_ai_list(escort_char, why):
    """Point AI_A_07's do-not-attack list at OUR escort instead of vanilla's Natasha.

    Sahnar is Joshua and Basil is Natasha, so Sahnar must play the way Joshua plays -- and
    half of how Joshua plays is a refusal. `AI_A_07` is
    `gAiScript_ActionInRange_ExceptNatasha`: it runs the standard offensive action through
    `AiIsUnitEnemyAndNotInScrList`, which calls `AiIsInShortList(script->unk_08, ...)` against
    each candidate's `pCharacterData->number`. `unk_08` is the list below, and vanilla declares
    it `u8 gUnknown_085A8A00[] = { CHARACTER_NATASHA, 0, 0, 0 }`. That is what makes vanilla's
    escort recruit survivable at all: the duelist stands on the arena tile with a Killing Edge
    and simply will not swing at the cleric walking up to talk him down.

    Copying Joshua's `.ai` bytes alone does NOT copy that, because the list holds a literal
    character id and our escort is not Natasha -- Basil takes Natasha as a STAT_DONOR but
    deploys on her own CHARACTER slot. Left alone, `0x7` degrades to plain `AI_A_00` and the
    fragile Cleric is a legal target. So the list is repointed here.

    SAFE BECAUSE THE LIST HAS EXACTLY ONE CLIENT. Swept over `events_udefs.c` at decomp HEAD
    (never the built tree -- our injections live there): `.ai = {0x7,` appears ONCE in all of
    FE8, on `UnitDef_088B5914`, vanilla Ch5's Joshua. `AI_A_07` exists to serve one unit in one
    chapter, and that chapter is the one ch05 is the 1:1 twin of, so repointing its list
    changes the behaviour of nothing else in the ROM.

    Read as u16 despite the u8 declaration -- `AiIsInShortList` takes `const u16*` and stops on
    a zero entry, so `{ id, 0, 0, 0 }` is the two-entry short list `{ id, TERMINATOR }` on a
    little-endian target. Every FE8 character id fits in the low byte, so the shape is kept
    rather than widened.
    """
    with open(CP_DATA_C, encoding='utf-8') as f:
        source = f.read()
    pattern = (r'(u8 CONST_DATA %s\[\] = \{ )CHARACTER_NATASHA(, 0, 0, 0 \};)'
               % ESCORT_SAFE_AI_LIST)
    source, count = re.subn(pattern, r'\g<1>%s\g<2>' % escort_char, source, count=1)
    if count != 1:
        sys.exit('ERROR: %s is not vanilla\'s { CHARACTER_NATASHA, 0, 0, 0 } in %s -- AI_A_07\'s '
                 'do-not-attack list moved or was already patched, so %s would go unprotected'
                 % (ESCORT_SAFE_AI_LIST, CP_DATA_C, why))
    with open(CP_DATA_C, 'w', encoding='utf-8') as f:
        f.write(source)


def escort_safe_ai_clients(campaign='rime-of-the-frostmaiden'):
    """Every enemy carrying AI_A_07 -- ch05's escort byte."""
    return safe_ai_clients(ESCORT_SAFE_AI_INDEX, campaign)


def assert_escort_safe_ai_has_one_client(ai_bytes):
    """Refuse the repoint if anything but our duelist has picked up AI_A_07.

    The list is GLOBAL, so its safety rests entirely on being single-client. Vanilla ships one
    user; if ANY chapter gives a second unit `AI_A_07`, that unit silently inherits "will not
    attack Basil" and this stops being a faithful copy of Joshua's refusal.

    Swept over EVERY chapter, not just ch05: the hazard is a FUTURE chapter reaching for
    `{0x7,` for its own reasons, which is precisely the case a ch05-only scan cannot see.
    """
    users = escort_safe_ai_clients()
    if users != ['ch05.sahnar'] or ai_bytes != '{0x7, 0x3, 0x9, 0x0}':
        sys.exit('ERROR: AI_A_07 (%s) must have exactly one client across ALL chapters -- '
                 'ch05 Sahnar. Got %s. The do-not-attack list is global; a second client '
                 'inherits our escort\'s immunity by accident.' % (ESCORT_SAFE_AI_LIST, users))



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
        cls = CH05_CLASS_IDS.for_entry(enemy)
        items = [CH05_ITEM_IDS[item.get('fe_base') or item['id']]
                 for item in enemy.get('inventory', [])]
        drop = enemy.get('item_drop')
        pid = (CH05_BOSS_PID if enemy.get('is_boss')
               else CH05_MOOSE_PID if enemy.get('is_miniboss')
               else CH05_GENERIC_PID)
        for index, (x, y) in enumerate(enemy['positions']):
            ai = enemy_ai_initialiser(chap, enemy, index)
            carried = list(items)
            dropper = bool(drop) and index == 0
            if dropper:
                carried = _items_with_drop_last(carried, CH05_ITEM_IDS[drop])
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
        {'ravisin': ('[OpenMidLeft]', _fid_tag(GUEST_PORTRAIT_MAP['ravisin']))})


def ch05_ravisin_taunt_message(chap):
    """Ravisin's one locked battle taunt -- the line she says when the fight starts.

    The ``vanilla 0x9C7`` label cites Saar's own taunt, which ours is the twin of with one word
    swapped (empire -> Frostmaiden); ch05 writes the body into its own Ch6 host block. Vanilla
    seats Saar on [OpenMidLeft] for 9C7, and a battle quote draws over the combat screen with
    nobody opposite her, so the mined seat carries over unchanged.
    """
    return boss_quote_message(chap, 'boss_battle', 'ravisin', GUEST_PORTRAIT_MAP['ravisin'],
                              CH05_RAVISIN_TAUNT_MSG, 1)


def ch05_ravisin_death_message(chap):
    """Ravisin's one locked death box, from the chapter event source of truth.

    The event's ``vanilla 0x9C8`` label cites the donor scene; ch05 writes the body to its
    own Ch6 host block. The separate enemy ``death_quote`` field predates the locked dialogue
    pass and is deliberately not consulted here.
    """
    return boss_quote_message(chap, 'boss_death', 'ravisin', GUEST_PORTRAIT_MAP['ravisin'],
                              CH05_RAVISIN_DEATH_MSG, 1, seat='[OpenMidRight]')


def ch05_sahnar_talk_messages(chap):
    """Render the locked Basil->Sahnar Talk recruit -- the chapter's payoff -- from the YAML.

    The event's ``vanilla 0x9CC`` label cites the scene we MINE (vanilla's own Natasha->Joshua
    recruit, which ours is the twin of). It is not the destination: the caller stores this at
    CH05_SAHNAR_TALK_MSG in ch05's Ch6 host block. Until this landed the id WAS 0x9CC, and the
    placeholder read as a bug rather than as prose -- our two speakers wear the Artur and Marisa
    slots, so vanilla's scene played its own faces and its own words at them.

    STAGING is the two-shot ch04's parley already uses, and for the same reason: the RECRUITER
    holds mid-left (the party's side) and the unit being turned holds mid-right, so the exchange
    reads as two people facing each other rather than one podium swapping faces. Basil is the
    Natasha-donor Cleric walked across under escort; Sahnar is the red crit-Myrmidon she turns.

    ON-MAP, so the body wraps at the talk bubble's pixel budget -- a wider line hits PutTalkBubble's
    unclamped right-side branch and runs off the tilemap (the ch03 crier bug). Consecutive turns
    by one speaker coalesce into a single [OpenX] block with the authored breaks kept as pages,
    so all sixteen A-presses survive.
    """
    _card, beats = _split_event_beats(
        chap, 'sahnar_talk', 'ch05 Basil->Sahnar Talk recruit', (CH05_SAHNAR_TALK_MSG,),
        card_required=False)
    beat = beats[0]
    speakers = {next(iter(entry)) for entry in beat}
    if len(beat) != 16 or not speakers <= {'sahnar', 'basil'}:
        sys.exit('ERROR: ch05 Talk recruit must remain the sixteen locked Sahnar/Basil boxes; '
                 'got %d boxes from %s' % (len(beat), sorted(speakers)))
    event = next(e for e in chap['events'] if e.get('trigger') == 'sahnar_talk')
    if 'no_lupin_fallback' not in event:
        sys.exit('ERROR: ch05 Talk recruit is a branched scene and must carry a '
                 'no_lupin_fallback -- without it the no-Lupin arm proves Sahnar with a wolf '
                 'the player may never have recruited')
    render = lambda script: _script_to_message(
        script,
        {'basil':  ('[OpenMidLeft]',  _fid_tag(PORTRAIT_MAP['basil'])),
         'sahnar': ('[OpenMidRight]', _fid_tag(PORTRAIT_MAP['sahnar']))})
    return locked_and_variant(
        beat, event['no_lupin_fallback'], render, 'ch05 Talk recruit no-Lupin fallback',
        (CH05_SAHNAR_TALK_MSG, CH05_SAHNAR_TALK_NO_LUPIN_MSG))


def _ch05_opening_scene(chap, slot, boxes, what, podiums, fid,
                        width=fe8_talk_font.TALK_BUDGET_PX):
    """One locked opening scene, box-counted and podium-checked, as a rendered message body.

    Shared by the three tomb scenes, the arrival (which brings its own podium set, being the
    first one the PARTY speaks in) and the join, so a further scene costs a table row rather
    than a second loop. `width` is the CHANNEL and nothing else -- a PIXEL budget, taken from
    `fe8_talk_font`: the talk bubble's for a faced beat, the auto-centered box's for faceless
    narration.
    """
    script = _chapter_event_by_slot(chap, 'chapter_start', slot,
                                    'ch05 opening (%s)' % what)['script']
    if _script_box_count(script) != boxes:
        sys.exit('ERROR: ch05 opening %r (%s) must remain the %d locked boxes; got %d'
                 % (slot, what, boxes, _script_box_count(script)))
    return script, _ch05_opening_body(script, slot, what, podiums, fid, width)


def _ch05_opening_body(script, slot, what, podiums, fid,
                       width=fe8_talk_font.TALK_BUDGET_PX):
    """Render one opening beat at its channel's width, refusing anyone with no podium.

    Staged names, not speakers: a character can be put on screen by `present:` and never take a
    line (ch05's scene 3 raises Sahnar that way), and they need a seat exactly as a speaker
    does. Reading the keys alone would let such a scene through and then die inside the
    renderer on a missing staging entry.
    """
    staged = _script_staged_names(script)
    unstaged = sorted(staged - set(podiums))
    if unstaged:
        sys.exit('ERROR: ch05 opening %r (%s) stages %s, which its podium table '
                 'gives no seat -- a speaker defaulted to mid-left is a speaker two '
                 'scenes can put in the same seat' % (slot, what, unstaged))
    assert_silent_faces_have_elbow_room(script, {k: podiums[k] for k in staged},
                                        'ch05 opening %r (%s)' % (slot, what))
    return _script_to_message(script, {k: (podiums[k], fid(k)) for k in staged}, width=width)


def _ch05_scene_and_variant(chap, slot_row, variant_msg, podiums, fid,
                            width=fe8_talk_font.TALK_BUDGET_PX):
    """A branched opening scene as its TWO rendered bodies: the locked one and its no-Lupin twin.

    Every ch05 fallback is this shape, which is the whole reason a fallback costs ONE id: the
    substituted boxes are spliced into a copy of the locked beat (`variant_beat`, which asserts
    each `replaces:` anchor so a re-ordered script fails loudly instead of swapping the wrong
    box) and the WHOLE variant scene goes to a second message, chosen at runtime by
    `branch_on_check_alive`. Splitting a scene around its differing box would cost one id per
    fragment -- duplicating text is free, ids are what is scarce.
    """
    slot, msg, boxes, what = slot_row
    script, body = _ch05_opening_scene(chap, slot, boxes, what, podiums, fid, width)
    event = _chapter_event_by_slot(chap, 'chapter_start', slot, 'ch05 opening (%s)' % what)
    if 'no_lupin_fallback' not in event:
        sys.exit('ERROR: ch05 opening %r (%s) is a branched scene and must carry a '
                 'no_lupin_fallback -- without it the no-Lupin arm plays the locked script, '
                 'which addresses a wolf who is not there' % (slot, what))
    fallback = variant_beat(script, event['no_lupin_fallback'],
                            'ch05 %s no-Lupin fallback' % what)
    return [(msg, body),
            (variant_msg, _ch05_opening_body(fallback, slot, what + ' (no Lupin)',
                                             podiums, fid, width))]


def ch05_opening_messages(chap):
    """The four locked scenes that open ch05, as (msg_id, body) in PLAYER order.

    Three at the tomb before the party arrives, then the arrival itself -- and the arrival is
    written TWICE, because it is the first scene with a `no_lupin_fallback`: the locked script
    at CH05_ARRIVAL_SLOT's id and the substituted variant at CH05_ARRIVAL_NO_LUPIN_MSG, one of
    which `branch_on_check_alive` plays. That is the whole cost of a fallback -- one extra id.

    Rendered at the talk budget like every faced scene: these play over a
    BACG with nothing staged on the field, which is vanilla Ch5's own channel for the same
    beats (see CH05_OPENING_SLOTS). A faced beat wrapped narrower would merely be needlessly
    narrow here -- the 29 exists for PutTalkBubble's unclamped right edge, and there is no
    bubble.

    Box counts are asserted per scene because the whole point of a locked script is that the
    wiring cannot quietly drift from it -- and because #25's own scene table has them wrong
    (it prices scenes 1 and 2 at 16 and 17; the YAML holds 19 and 16).
    """
    # Sephek's face comes from PROLOGUE_SEPHEK_SLOT, NOT from GUEST_PORTRAIT_MAP, and the two
    # disagree on purpose-built spelling rather than on which slot: the map says 'O_Neill' (a
    # portrait-slot name, used for dressing busts) while the FID tag textdefs.txt actually
    # defines is [FID_ONeill]. _fid_tag special-cases 'ONEILL' and cannot reach the other
    # spelling, so routing his face through the map emits [FID_O_Neill] -- a tag that does not
    # exist. He is the prologue's boss returning, so the prologue's constant is the right one.
    fid = _make_fid({'sephek': _fid_tag(PROLOGUE_SEPHEK_SLOT),
                     'ravisin': _fid_tag(GUEST_PORTRAIT_MAP['ravisin'])},
                    'ch05 opening: unknown cutscene speaker')
    out = []
    for slot, msg, boxes, what in CH05_OPENING_SLOTS:
        _script, body = _ch05_opening_scene(
            chap, slot, boxes, what,
            dict(CH05_OPENING_PODIUMS, **CH05_OPENING_PODIUM_OVERRIDES.get(slot, {})), fid)
        out.append((msg, body))
    # Scene 4, and its no-Lupin twin. The party speaks here for the first time, so it brings its
    # own podium table; the variant is the SAME beat with box 1 substituted, rendered through the
    # same body writer at the same seats.
    out += _ch05_scene_and_variant(chap, CH05_ARRIVAL_SLOT, CH05_ARRIVAL_NO_LUPIN_MSG,
                                   CH05_ARRIVAL_PODIUMS, fid)
    return out


def ch05_basil_join_messages(chap):
    """Scene 5 -- Basil's join -- and its no-Lupin twin, as (msg_id, body) pairs.

    The opening's first ON-MAP beat, so it renders at the talk bubble's budget and not the backdrop
    scenes' 42: `PutTalkBubble`'s right-side branch computes x = 29 - width with no clamp, so a
    wider line runs off the tilemap (the ch03 crier bug). Everything else is the arrival's
    machinery unchanged, which is the point of `_ch05_scene_and_variant`.

    The substituted box is her SECOND, where she reads Lupin -- "...Wolf. You're hers. Awoken.
    But you're free? With them?" On the no-parley path there is no wolf to read, so the variant
    makes the PARTY itself the revelation instead: everyone Basil has ever met belonged to
    Ravisin, so people who belong to nobody are the whole surprise. Boxes 1 and 3 -- the tourist
    joke and the ask the CUSA answers -- are shared by both arms.
    """
    return _ch05_scene_and_variant(
        chap, CH05_BASIL_JOIN_SLOT, CH05_BASIL_JOIN_NO_LUPIN_MSG,
        CH05_BASIL_JOIN_PODIUMS,
        _make_fid({}, 'ch05 join: unknown cutscene speaker'))


def ch05_sahnar_alone_message(chap):
    """Scene 6 -- Sahnar alone at the sarcophagus -- as one (msg_id, body) pair.

    ONE arm, so this is `_ch05_opening_scene` rather than `_ch05_scene_and_variant`: she has
    never met the wolf and never mentions him, so there is nothing for a no-Lupin branch to
    substitute and the scene costs one id.

    Rendered at the talk bubble's budget. That is the twin's channel
    taken whole: vanilla plays its 0x9C3 as a bare `TEXTSHOW` over the map with Joshua standing
    on this same tile. Until 2026-08-14 ours could not, because Sahnar did not exist on the
    field until the turn-2 eruption; the scene-3 summon is what put her there.
    """
    slot, msg, boxes, what = CH05_SAHNAR_ALONE_SLOT
    _script, body = _ch05_opening_scene(
        chap, slot, boxes, what, CH05_SAHNAR_ALONE_PODIUMS,
        _make_fid({}, 'ch05 scene 6: unknown cutscene speaker'))
    return [(msg, body)]


def ch05_moose_charge_message(chap):
    """Scene 7 as TWO (msg_id, body) pairs, split across the bellow.

    The question and the punchline are separate messages because the beat between them is a
    SCENE CHANGE: the full-screen CG needs `REMOVEPORTRAITS`, that tears the talk down, and a
    `[BreakTalk]` pause cannot survive it (filmed 2026-08-15 -- the CG played, the charge played,
    and the quip never appeared). One `stage_cut:`, two ids, and the second is what the bellow
    costs. Both render at the talk bubble's budget -- on-map beats either side of the image.

    One arm, so no variant: the moose is ch04's quarry and Lupin's presence changes nothing
    about it (Pinky is the party's other tracker and asks on either path).
    """
    slot, msg, boxes, what = CH05_MOOSE_CHARGE_SLOT
    script = _chapter_event_by_slot(chap, 'chapter_start', slot,
                                    'ch05 opening (%s)' % what)['script']
    if _script_box_count(script) != boxes:
        sys.exit('ERROR: ch05 scene 7 must remain the %d locked boxes; got %d'
                 % (boxes, _script_box_count(script)))
    ask, _direction, quip = split_on_stage_cut(script, 'ch05 scene 7')
    fid = _make_fid({}, 'ch05 scene 7: unknown cutscene speaker')
    return [(msg, _ch05_opening_body(ask, slot, what + ' (the question)',
                                     CH05_MOOSE_CHARGE_PODIUMS, fid)),
            (CH05_MOOSE_QUIP_MSG,
             _ch05_opening_body(quip, slot, what + ' (the punchline)',
                                CH05_MOOSE_CHARGE_PODIUMS, fid))]


def ch05_moose_station(chap):
    """(pen, charge_from, charge_route) for the white moose -- where it fights, and how it breaks.

    THE PEN IS THE ONE THAT MATTERS MECHANICALLY: it is the parity-locked position the difficulty
    read is grounded on (threat 14.1, cornered against the map's top edge), so everything else
    here is cutscene staging that gets undone. The moose is placed on `charge_from` off camera,
    runs `charge_route`, and is snapped back to the pen before the map goes live.

    All three are required rather than defaulted, for the reason Sahnar's `walks_to` is: a
    missing one is invisible to every check we have and would quietly turn a staged beat into a
    repositioning -- which on this unit means handing the player a threat-14 monster somewhere
    the chapter was never balanced for.
    """
    moose = next(e for e in chap['enemy_units'] if e['id'] == 'white-moose')
    pen = tuple(moose['positions'][0])
    for field in ('charge_from', 'charge_route'):
        if field not in moose:
            sys.exit('ERROR: ch05\'s white moose has no `%s` -- scene 7 is a setup and a '
                     'punchline across the charge, and with nowhere to charge from or to the '
                     'beat is two lines and a pause' % field)
    route = tuple(tuple(point) for point in moose['charge_route'])
    if route[-1] == pen:
        sys.exit('ERROR: ch05\'s moose charge ENDS on its pen %r, so the snap-back is a no-op '
                 'and the lunge is never undone on screen -- the route is meant to run PAST the '
                 'pen at the party' % (pen,))
    return pen, tuple(moose['charge_from']), route


def ch05_party_camera_tile(chap):
    """The tile scene 7 cuts back to: vanilla's own `CAMERA(5, 18)` for this same beat.

    Asserted against our `deploy_slots` rather than trusted, because the retile is what makes
    vanilla's number ours: ch05 lifts Ch5's nine player start tiles 1:1, so (5,18) is a tile the
    party is standing on -- but a future re-paint that moved the pocket would leave this framing
    an empty corner, silently, with nothing else complaining.
    """
    tile = (5, 18)
    slots = {tuple(s) for s in chap['deployment']['deploy_slots']}
    if tile not in slots:
        sys.exit('ERROR: ch05 scene 7 frames the party at %r, which is no longer one of the '
                 'chapter\'s deploy_slots %s -- the last shot before turn 1 would hold on an '
                 'empty tile' % (tile, sorted(slots)))
    return tile


def ch05_sahnar_station(chap):
    """(load tile, fighting tile) for Sahnar -- vanilla's (12,6) then (9,7).

    Two tiles, not one, and the second is the one that matters mechanically: the load tile is
    the ARENA, and she may not stay on it (see CH05_SAHNAR_ALONE_SLOT). `walks_to` is required
    rather than defaulted, because a missing walk-off is invisible in every check we have and
    costs the chapter its arena.
    """
    sahnar = next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')
    load = tuple(sahnar['positions'][0])
    if 'walks_to' not in sahnar:
        sys.exit('ERROR: ch05 Sahnar has no `walks_to` -- she LOADs on the arena tile %r, which '
                 'is the arena tutorial\'s own AREA trigger, so without a walk-off she blocks '
                 'the arena for the entire chapter' % (load,))
    return load, tuple(sahnar['walks_to'])


def ch05_sahnar_alone_block(sahnar_table, sahnar_char, position, station):
    """Scene 6, played after the join: the camera finds the arena, and Sahnar is standing on it.

    Vanilla's own after-prep beat, copied down to the order of its commands -- `CUMO_AT` the
    arena tile FIRST, then `LOAD1`, so the player watches the duelist arrive rather than
    discovering her already there, then `MOVE` her off it before she speaks. The walk-off is
    not flourish: the load tile IS the arena, and a hostile parked on it makes the arena
    unenterable all chapter (see CH05_SAHNAR_ALONE_SLOT).

    No `FADU` of its own -- scene 5 already brought the screen up after the prep prologue's
    fade to black, and this beat follows it in the same event list without going dark between.

    This is also where `arrives_turn: 2` stopped being ours (#25, Nicolas 2026-08-14): Sahnar
    is on the map from turn 1, exactly as vanilla's Joshua is, and the eruption keeps its six
    reinforcements without her.

    THE `CAMERA` IS NOT DECORATION AND WAS MISSING UNTIL 2026-08-14. `CUMO_AT` draws a cursor
    and nothing else -- `EventDisplayCursor_Loop` calls `PutMapCursor` and returns -- so this
    beat was framed by whatever `LOMA` happened to leave, which is the map's north-west and
    happens to hold the arena. It looked right on film and was resting on an accident: anything
    that moved the reload origin would have played the scene off-screen with no error anywhere.
    Vanilla pairs the two here too (`CAMERA(0, 0)` ahead of its own `CUMO_AT(12, 6)`), and ours
    now names the tile it actually wants rather than inheriting a corner.
    """
    _slot, msg, _boxes, what = CH05_SAHNAR_ALONE_SLOT
    (x, y), (gx, gy) = station
    return ('    CAMERA(%d, %d) /* the SCROLL -- CUMO alone only draws a cursor */\n'
            '    CUMO_AT(%d, %d) /* the arena tile -- vanilla frames it before she arrives */\n'
            '    STAL(60)\n'
            '    CURE\n'
            '    LOAD1(0x1, %s) /* Ravisin called her up in scene 3; here she rises */\n'
            '    ENUN\n'
            '    MOVE(0x0, %s, %d, %d) /* ...and OFF the arena tile, as vanilla walks Joshua:\n'
            '                             (%d,%d) is the tutorial\'s own AREA trigger and a unit\n'
            '                             standing on it locks the arena for the whole chapter */\n'
            '    ENUN\n'
            '    CUMO_CHAR(%s) /* the bubble anchors to a unit -- Sahnar at her post */\n'
            '    STAL(60)\n'
            '    CURE\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X) /* 6 -- %s */\n'
            '    TEXTEND\n'
            '    REMA\n'
            % (x, y, x, y, sahnar_table, sahnar_char, gx, gy, x, y, sahnar_char, msg, what))


def ch05_moose_to_corner(moose_pid, start):
    """Put the moose on its run's starting corner, instantly, WHILE THE SCREEN IS BLACK.

    It fights from the pen and it runs from the corner, so something has to move it between
    the two, and a negative-speed `MOVE` is vanilla's own instant reposition (`ch14a` resets
    Carlyle this way). What matters is WHEN: this used to sit inside the beat, after the
    screen was already up, and Nicolas caught it on film -- "I think I saw the moose teleport
    from its top middle to top right spot right as it loaded in" (2026-08-15). He did. An
    instant move is only invisible if nothing can see it.

    So it is emitted immediately after the turn-1 line LOADs, where the screen is still faded
    out in both the shipping opening (which ends its backdrop half on a FADI) and the debug
    boot. Being a separate emitter is the point: the call site is the constraint.
    """
    return ('    MOVE(0xffff, %s, %d, %d) /* to the run\'s corner, instantly and UNSEEN -- the\n'
            '                                screen is still black here. The pen it fights from\n'
            '                                is the map\'s top edge, so the run needs somewhere\n'
            '                                to start that is not the pen. */\n'
            '    ENUN\n' % (moose_pid, start[0], start[1]))


def ch05_moose_charge_block(moose_pid, station, party_tile):
    """Scene 7, the last beat before turn 1: Pinky asks, the moose answers, the fight starts.

    `CAMERA` IS THE SCROLL AND `CUMO` IS ONLY A POINTER. `EventDisplayCursor_Loop` (eventscr.c)
    calls `PutMapCursor` and nothing else -- it never moves the view -- so a CUMO on its own
    frames whatever the last CAMERA left, which after `LOMA` happens to be the map's north and
    is why the beats above it look framed. Vanilla pairs the two at this exact beat
    (`CAMERA(5, 18)` then `CUMO_CHAR` ahead of its own 0x9C4), and the first cut of this wiring
    did not: it shipped a `CUMO_AT` where the party framing was meant and the film simply never
    cut south (caught 2026-08-14 by watching the run, not by reading it).

    ONE camera position for the whole message, and that is forced rather than chosen.
    `[BreakTalk]` only LOCKS the talk proc (scene.c `case 0x04`) -- the bubble stays up and the
    faces stay loaded across the gap -- so a camera move inside the message would scroll the map
    out from under an open bubble whose tail points at nothing. The frame therefore goes where
    the LINE is about: the moose's pen, so the player is looking at the thing Pinky is asking
    about while he asks it, and the charge that answers him plays in the same shot. Only after
    `REMA` does it cut south, which is also how the map comes up on the party for turn 1.

    THE CHARGE IS NET-ZERO, and it is bracketed by two INSTANT moves to make that true. The moose
    is put on `charge_from` before the camera arrives and snapped back to the pen after `REMA`,
    both with a NEGATIVE speed -- `Event2F_MoveUnit` short-circuits speed < 0 to a bare
    `MoveUnit_`, vanilla's own off-screen reposition (`ch14a` resets Carlyle with
    `MOVE(0xffff, ...)` twice around one scene). Between them it runs an AUTHORED multi-leg route
    (`reda_route_move`), because the path is the beat: it starts in the top-right corner, runs
    left along the rim and turns down at the party, so it changes direction on screen instead of
    sliding four tiles in a straight line (Nicolas, 2026-08-15 -- the first cut was over before
    it read). The fight still begins from the parity-locked pen.

    The pen being on the map's TOP EDGE is what forces this shape. Nicolas's first ask was to
    start further back and charge INTO the pen; there is no tile behind row 0, so the run goes
    forward THROUGH the pen and is put back instead.

    The music DUCKS under the bellow and is restored with the map -- `MUSI`/`MUNO`, the pair
    ch05's reliquary visits already use. It is worth naming the wrong answer too, because it
    reads as the right one: fading the SILENT song in is a REPLACEMENT, not a duck, and it left
    the chapter playing from turn 1 with nothing at all and no way back. No test, verdict or
    film catches that; Nicolas asking whether the music returns is what caught it.
    The moose does not speak, and it never has -- locked 2026-07-03 and re-locked by this chapter.

    NO unit is named for the camera on the party side, and that is deliberate. ch05 deploys 9 of
    a 10-unit pool, so BOTH of this scene's speakers can be benched, and `CUMO_CHAR` on a benched
    unit finds a `US_NOT_DEPLOYED` body at stale coordinates and pans to it. `CUMO_AT` takes a
    tile. (The bubble does not need a unit either way -- `StartTalkOpen` anchors it to the
    speaking FACE SLOT, not to anything on the map.)
    """
    _slot, msg, boxes, what = CH05_MOOSE_CHARGE_SLOT
    (px, py), (sx, sy), route = station
    ax, ay = party_tile
    run = '\n'.join(reda_route_move(
        moose_pid, route, 'it breaks -- left along the rim, then down at them',
        who='the ch05 white moose'))
    return ('    CAMERA(%d, %d) /* the SCROLL -- CUMO alone only draws a cursor */\n'
            '    CUMO_AT(%d, %d) /* the rim: the moose at bay among the standing dead */\n'
            '    STAL(60)\n'
            '    CURE\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X) /* %d -- %s */\n'
            '    TEXTEND\n'
            '    REMA /* the talk ENDS here rather than pausing: the bellow is a scene change\n'
            '            and a locked talk does not survive one (filmed 2026-08-15) */\n'
            '    MUSI /* DUCK the music under the bellow (EvtSetVolumeDown); it is un-ducked\n'
            '            once the map is back. This used to fade the silent song in instead,\n'
            '            which is a REPLACEMENT and not a duck -- it left the chapter playing\n'
            '            from turn 1 with no music and nothing able to bring it back. Caught by\n'
            '            Nicolas asking whether the music returns (2026-08-15); vanilla never\n'
            '            ends a beginning scene on silence. The reliquary visits use this same\n'
            '            pair around their own backdrop. */\n'
            '    FADI(16) /* fade the MAP out first. Without this the image swaps in under a\n'
            '                lit screen and the beat reads as a glitch rather than a cutaway\n'
            '                (Nicolas, 2026-08-15: "jumpy/glitchy both in and out of it"). */\n'
            '    REMOVEPORTRAITS /* re-arms the BACG load mode AND clears the faces, so the\n'
            '                       CG comes up on a clean screen rather than behind Pinky */\n'
            '    BACG(%s) /* THE BELLOW: the moose, full screen. A bust could never hold\n'
            '                those antlers -- a 96x80 portrait is drawn inside the talk\n'
            '                window\'s envelope, and a BACG owns all 240x160. */\n'
            '    FADU(16) /* ...and fade the moose IN */\n'
            '    SOUN(%s) /* THE BELLOW. Nicolas picked it by ear off the audition page:\n'
            '        `mon_mdg_critical1`, the beast critical -- "the most moosy" (2026-08-15).\n'
            '        It is 1.2s long, which is what STAL(90) below is sized to.\n'
            '        FINDING IT AT ALL took correcting a wrong table: `banim_code_sound_*` in\n'
            '        banim_code.inc encodes 0x850000XX and XX is NOT a song id, so reading it\n'
            '        as one auditioned `se_sys_hp2` -- an HP-bar tick -- as a monster roar.\n'
            '        Song ids come from sound/song_table.s and nowhere else. */\n'
            '    EARTHQUAKE_START(0, 0) /* the weight, UNDER the cry. The 0 is `playse` OFF and\n'
            '        it has to be: StartEventEarthQuake fires PlaySoundEffect(SONG_26A) the\n'
            '        instant it starts, on the same channel, so with it on the rumble PREEMPTS\n'
            '        the roar and the animal is never heard -- which is exactly what happened\n'
            '        the first two times this was filmed. The shake carries the weight the\n'
            '        rumble used to; they cannot both sound without one killing the other.\n'
            '        WHAT it shakes is chosen by `activeTextType`, not by us: Event42_EarthQuake\n'
            '        maps 0/3/4 to a map-view shake and 1 to a BG-position shake, and\n'
            '        REMOVEPORTRAITS above set it to 1 -- so the judder lands on the BG layer,\n'
            '        which right now IS the moose. The image itself shakes.\n'
            '        !! 2 and 5 return EVC_ERROR, which does not advance the event pointer and\n'
            '        therefore HANGS the chapter. This ordering is load-bearing. */\n'
            '    STAL(90) /* the cry plays out -- 1.2s of sample, 90 frames of hold */\n'
            '    EARTHQUAKE_END /* ends the shake AND fades the SE channel (Sound_FadeOutSE),\n'
            '                      so it belongs against the picture fading and not mid-cry */\n'
            '    FADI(16) /* fade the moose out again */\n'
            '    CLEAN /* ...and back to the map. CLEAN is the whole restore and it is NOT\n'
            '             optional: `EventScr_RemoveBGIfNeeded` only fades, conditionally, so\n'
            '             without this the map returns wearing the CG\'s PALETTE -- filmed\n'
            '             2026-08-15, a snowfield in moose-red. Vanilla\'s own order, from\n'
            '             EventScr_TextShowWithFadeIn: fade down, clean, fade up. */\n'
            '    MUNO /* ...and the music back up with the map (EvtUnsetVolumeDown) */\n'
            '    FADU(16) /* ...and fade the map back up. Symmetric with the way in: this is\n'
            '                 vanilla\'s own backdrop shape, the one the ch05 opening uses\n'
            '                 between its scenes, and the only one that does not read as a\n'
            '                 hitch on either side. */\n'
            '%s\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X) /* ...and Meesmickle answers the question sideways */\n'
            '    TEXTEND\n'
            '    REMA\n'
            '    CAMERA(%d, %d) /* cut south -- vanilla\'s own framing ahead of this beat */\n'
            '    CUMO_AT(%d, %d) /* back on the party at the stair-foot, off the rim */\n'
            '    STAL(30)\n'
            '    CURE\n'
            '    MOVE(0xffff, %s, %d, %d) /* Ravisin\'s hold snaps it back to the pen, instantly\n'
            '                                and with the camera already south. The fight starts\n'
            '                                from the locked tile. */\n'
            '    ENUN\n'
            % (sx, sy, sx, sy, msg, boxes, what,
               CH05_MOOSE_BELLOW_BG, CH05_MOOSE_BELLOW_SFX, run, CH05_MOOSE_QUIP_MSG,
               ax, ay, ax, ay, moose_pid, px, py))


def ch05_opening_backdrop_block():
    """The event-script head that plays ch05's four opening scenes before the map is built.

    ch03/ch04's shape, not a chain of `Text_BG` calls, and the difference is load-bearing:
    `Text_BG` expands to a CALL that ends in `EventScr_TextShowWithFadeIn` -- CLEAN, then
    FADU(16) back onto the MAP. Before `LOMA` our map is still the host slot's, so each scene
    would fade up onto vanilla Ch6's terrain between beats. One BACG held across all three,
    faded through black between scenes, keeps vanilla's separation without that.

    The fade between scenes is not decoration. They are three separate moments (Basil at the
    sarcophagus; Sephek and Ravisin elsewhere in the tomb; Ravisin alone after he leaves), and
    vanilla separates its equivalents with a full `Text_BG` fade cycle apiece. Played as a hard
    cut they would read as one continuous conversation.

    Then scene 4 CUTS to a second backdrop, which is a different kind of seam and inherited from
    the same twin: the first three are the tomb, and this one is the ridge above it, so vanilla's
    own BG_SERAFEW_VILLAGE -> BG_TOWN switch at the arrival beat is the model. A second `BACG`
    needs its load mode re-armed first (the `REMOVEPORTRAITS` below) -- `EventShowTextBgDirect`
    only decompresses while `activeTextType` is REMOVEPORTRAITS/_1A22, and every `Text()` above
    left it at TEXTSTART, so a bare second BACG is a no-op that leaves the tomb on screen. That
    is the ch03/ch04 stale-BG bug, and ch04's own opening carries the same re-arm.

    Scene 4 is also ch05's first BRANCH: its opening line is Lupin's, and ch04's parley is
    optional, so `branch_on_check_alive` picks between the locked scene and the variant whose
    box 1 goes to Pinky. The test is the ROSTER, which is what makes it survive ch05's 9-of-10
    deploy -- see branch_on_check_alive.
    """
    scenes = []
    for i, (_slot, msg, _boxes, what) in enumerate(CH05_OPENING_SLOTS):
        if i:
            # Fade THROUGH black between moments. The BACG stays in VRAM, so the pair needs no
            # second BACG -- and re-issuing one here would be a no-op anyway (see the docstring).
            # Scene 2 is Sephek's orders, vanilla's Glen->Saar: its plotters' Solve the Riddle
            # starts there and carries scene 3 (ADR 0336).
            riddle = ('    MUSC(SONG_SOLVE_THE_RIDDLE) /* the plotters, as vanilla Ch5\'s */\n'
                      if i == 1 else '')
            scenes.append('    FADI(16)\n' + riddle
                          + '    FADU(16) /* a separate moment, same place */\n')
        scenes.append('    Text(0x%X) /* %d -- %s */\n' % (msg, i + 1, what))
    _slot, arrival_msg, _boxes, arrival_what = CH05_ARRIVAL_SLOT
    return ('    REMOVEPORTRAITS\n'
            '    BACG(%s) /* the elven tomb, before the party arrives */\n'
            '    FADU(16)\n' % CH05_OPENING_BG
            + ''.join(scenes)
            + '    MUSCMID(SONG_SILENT) /* the plotters\' music ends with the tomb */\n'
              '    FADI(16) /* fade the tomb out; the party arrives elsewhere */\n'
              '    REMOVEPORTRAITS /* re-arm BACG BG-load mode (Text() reset it to TEXTSTART) */\n'
              '    BACG(%s) /* CUT to the ridge above the hollow */\n'
              '    MUSC(SONG_ADVANCE) /* the party arrives: vanilla Ch5\'s march */\n'
              '    FADU(16)\n' % CH05_ARRIVAL_BG
            + branch_on_check_alive(
                CH05_LUPIN_CHARACTER,
                '    Text(0x%X) /* 4 -- %s */\n' % (arrival_msg, arrival_what),
                '    Text(0x%X) /* 4 -- no Lupin: Pinky reads the trail instead */\n'
                % CH05_ARRIVAL_NO_LUPIN_MSG)
            + '    FADI(16) /* fade the ridge out; LOMA builds the real map next */\n')


def ch05_basil_join_block(basil_char):
    """Scene 5, played AFTER the prep CALL: the map comes up, Basil speaks, Basil joins.

    Vanilla puts this beat's twin (0x9C2) BEFORE its prep CALL and we cannot, which is the one
    place ch05's inherited channel had to be overruled. Vanilla LOAD1s Eirika's group onto the
    street first, so its street scenes have a party to play to; ours arrives through Pick Units
    (the ally table is never LOADed on a prep chapter -- decisions.md "How the deploy cap + prep
    screen are actually wired"), so before the CALL the field holds sixteen risen dead, Ravisin,
    and a green shrub addressing an empty pocket. After it, the nine the player chose are
    standing at the stair-foot and Basil is at the pocket's mouth two tiles above them.

    The shape is then vanilla's own after-prep block, which is what its 0x9C3/0x9C4 are:
    `FADU(16)` -- the shared prep prologue fades to black and leaves it there, so anything
    VISIBLE after the CALL brings its own fade-up -- then CUMO/STAL/CURE to put the camera on
    the speaker (`PutTalkBubble` anchors to a unit, and hers is the only face here), then the
    branch, then the `CUSA` that was already the last thing this script did. The join text and
    the join itself are now one beat: she asks to be taken to Sahnar on box 3 and turns the
    party's colours on the next command.
    """
    _slot, msg, _boxes, what = CH05_BASIL_JOIN_SLOT
    beat = lambda m, why: ('    TEXTSTART\n'
                           '    TEXTSHOW(0x%X) /* 5 -- %s */\n'
                           '    TEXTEND\n'
                           '    REMA\n' % (m, why))
    return ('    FADU(16) /* the prep prologue left the screen black; scene 5 is VISIBLE */\n'
            '    CUMO_CHAR(%s) /* the bubble anchors to a unit -- Basil at the pocket mouth */\n'
            '    STAL(60)\n'
            '    CURE\n' % basil_char
            + branch_on_check_alive(
                CH05_LUPIN_CHARACTER,
                beat(msg, what),
                beat(CH05_BASIL_JOIN_NO_LUPIN_MSG,
                     'no Lupin: the PARTY is the revelation instead'),
                label_base=CH05_BASIL_JOIN_LABEL_BASE))


def ch05_moose_debug_script(chap, seed_load):
    """`--ch05-moose`: New Game straight into scene 7, and NOTHING else.

    THE STANDING RULE, applied late (Nicolas, 2026-08-15). Scene 7 is the last beat of a
    ~52-A-press opening, so every film of it replayed four backdrop scenes, Preparations, the
    join and Sahnar's monologue -- roughly four and a half minutes of scenes he had already
    signed off -- to reach ten seconds of moose. He stopped the third run himself. Iteration on a
    late beat has to be COMPILE-TIME ONLY; the debug boot is what makes it so, and it should have
    been the first thing built rather than the fourth.

    Keeps only what the beat cannot do without: `LOMA` to build the map, the turn-1 line (which
    is where the MOOSE comes from), and the boot seed (so the closing cut south has a party to
    land on). No backdrops, no prep CALL, no scenes 5-6, no Basil.

    `--ch05-boot` is a prerequisite and not a nicety: without its seed there is no party, and
    without prep nothing else would place one.
    """
    if not seed_load:
        sys.exit('ERROR: --ch05-moose needs --ch05-boot -- it skips Preparations, so the boot '
                 'seed is the only thing that puts a party on the map')
    return ('{\n'
            '    MUSC(SONG_DISTANT_ROADS) /* scene 7\'s cue, so the boot hears what ships */\n'
            '    SVAL(EVT_SLOT_B, 0x0)\n'
            '    LOMA(0x%X) /* build the ch05 map fresh */\n' % CH05_HOST_INDEX
            + '    LOAD1(0x1, %s) /* the 16 risen tomb-guard -- the MOOSE is one of them */\n'
              '    ENUN\n' % CH05_LINE_TABLE
            + seed_load
            + ch05_moose_to_corner(CH05_MOOSE_PID, ch05_moose_station(chap)[1])
            + '    FADU(16) /* no prep prologue to inherit a fade from -- and it comes AFTER\n'
              '                the reposition above, so that is never on screen */\n'
            + ch05_moose_charge_block(CH05_MOOSE_PID, ch05_moose_station(chap),
                                      ch05_party_camera_tile(chap))
            + '    ENUT(8)\n    EVBIT_T(7)\n    ENDA\n}')


def ch05_ending_debug_script(chap, seed_load, arm, basil_char, sahnar_table, sahnar_char):
    """`--ch05-ending=<arm>`: New Game straight into the ending, in one named roster state.

    THE STANDING RULE (decisions.md -> "Playtest runs are the most expensive thing in this
    repo", rule 3), applied BEFORE the first film this time rather than after the third. The
    ending is the last thing in the chapter: reaching it the honest way is the whole opening,
    Preparations, and a boss kill, and there are SIX of them to look at -- three roster arms
    times the Lupin flag. Filming that way would replay an hour of approved footage.

    Keeps only what the scene reads: `LOMA` for a map to load units onto, the boot seed (the
    ending hands the Guiding Ring to CHAR_EVT_PLAYER_LEADER, so there has to be a party), and
    whichever of Basil and Sahnar the named arm wants -- BLUE, because that is the state the
    real path leaves them in. Then a `FADU` so the ending's own opening `FADI` has a map to
    take down, exactly as it does on the real path, and the ending event list itself.

    The arms map one-for-one onto the three questions the scene asks:
      * `full`       -- Basil alive, Sahnar recruited and alive: scene 16, all three beats
      * `no-sahnar`  -- Basil alive, Sahnar never turned: scene 16 with beat B skipped
      * `basil-died` -- neither: scene 17
    and `--ch05-lupin` picks beat C's arm on top of any of them.

    THE PAYOUT IS ALWAYS ARMED. The four reliquary flags are set here whatever the arm, because
    the give's placement relative to the fade is one of the things this boot exists to look at:
    `GIVEITEMTO` opens a BLOCKING convoy menu on a full pack, and behind a `FADI` the player
    operates it blind. `ch05crest` already proves the gating itself, so nothing is lost by not
    exercising the un-paid path here.
    """
    if not seed_load:
        sys.exit('ERROR: --ch05-ending needs --ch05-boot -- it skips Preparations, so the boot '
                 'seed is the only thing left that puts a party on the map, and the ending '
                 'hands its reward to the party LEADER')
    if arm not in CH05_ENDING_ARMS:
        sys.exit('ERROR: --ch05-ending arm %r is not one of %s'
                 % (arm, ', '.join(CH05_ENDING_ARMS)))
    stage = ''
    if arm != 'basil-died':
        stage += ('    LOAD1(0x1, %s) /* Basil, at the pocket mouth */\n    ENUN\n'
                  '    CUSA(%s) /* -> blue: the real path joins her in scene 5 */\n'
                  % (CH05_BASIL_TABLE, basil_char))
    if arm == 'full':
        stage += ('    LOAD1(0x1, %s) /* Sahnar, on the arena tile */\n    ENUN\n'
                  '    CUSA(%s) /* -> blue: the real path turns her on Basil\'s Talk */\n'
                  '    ENUT(%s) /* ...and the Talk sets its CHAR flag, which the berry beat '
                  'reads */\n'
                  % (sahnar_table, sahnar_char, CH05_SAHNAR_TALK_FLAG))
    payout = ''.join('    ENUT(%s) /* %s saved */\n'
                     % (CH05_VILLAGE_FLAGS[v['id']], v['id'])
                     for v in chap.get('villages', []))
    return ('{\n'
            '    MUSC(SONG_TENSION)\n'
            '    SVAL(EVT_SLOT_B, 0x0)\n'
            '    LOMA(0x%X) /* build the ch05 map fresh */\n' % CH05_HOST_INDEX
            + seed_load
            # No Lupin load, and that is not an omission: neither ending branches on him any
            # more (see CH05_ENDING_MSGS). It DID need one while they did -- he is not in the
            # boot seed, so a CH05LUPIN=1 ROM would have answered CHECK_ALIVE with 0 and filmed
            # the no-Lupin arm under the other name. That trap died with the branch.
            + stage
            + payout
            + '    FADU(16) /* the ending opens on a FADI; give it the map to take down */\n'
              '    CALL(%s) /* ...and it ends on MNTS, so nothing follows */\n'
              '    ENDA\n}' % CH05_ENDING_SCRIPT)


def ch05_beginning_script(chap, basil_char, sahnar_table, sahnar_char,
                          seed_load='', lupin_load='', moose_only=False, ending_arm=None):
    """`CH05_BEGINNING_SCRIPT` end to end: the opening's seven-scene spine around LOMA and prep.

    Assembled here rather than inline in the injector so the ORDER is testable without a build --
    it is the first thing a reader loses, and it is load-bearing four times over: the backdrop
    scenes must precede `LOMA` (they end faded to black, which is what `LOMA` wants anyway), the
    join must FOLLOW prep (see `ch05_basil_join_block`), scene 6 must follow the join (it is the
    next beat in player order and it inherits the join's fade-up rather than bringing its own),
    and the two `CHECK_ALIVE` branches share one event list, so their labels must not collide.

    `seed_load`/`lupin_load` are the proof-ROM injections (`--ch05-boot`, `--ch05-lupin`) and are
    empty on the shipping build. `moose_only` is `--ch05-moose`, the scene-7 debug boot -- see
    `ch05_moose_debug_script` for why a late beat gets one.
    """
    if moose_only:
        return ch05_moose_debug_script(chap, seed_load)
    if ending_arm:
        return ch05_ending_debug_script(chap, seed_load, ending_arm,
                                        basil_char, sahnar_table, sahnar_char)
    return ('{\n'
            '    MUSC(SONG_TENSION)\n'
            + lupin_load
            # The BACKDROP half (#25): scenes 1-4, before the party arrives and before there is
            # any map of ours to stand on. Vanilla Ch5 opens the same way.
            + ch05_opening_backdrop_block() +
            '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
            '    LOMA(0x%X) /* RestartBattleMap -- build the ch05 map fresh */\n'
            % CH05_HOST_INDEX
            + '    LOAD1(0x1, %s) /* the 16 risen tomb-guard */\n    ENUN\n'
            % CH05_LINE_TABLE
            # ...and the moose straight to scene 7's starting corner, here where the screen is
            # still black rather than inside the beat, where it read as a teleport.
            + ch05_moose_to_corner(CH05_MOOSE_PID, ch05_moose_station(chap)[1])
            + '    LOAD1(0x1, %s) /* Basil, GREEN at the pocket mouth */\n    ENUN\n'
            % CH05_BASIL_TABLE
            + seed_load
            # NO FADU here: the shared prep prologue fades to black itself before drawing
            # Preparations, so revealing the freshly-LOMA'd map now only flashes it.
            + '    CALL(%s) /* preparations: pick %d; lord force-deployed */\n'
            % (CH05_PREP_SCRIPT, chap['deployment']['deploy_limit'])
            # Scene 5 and the join, AFTER Preparations and deliberately so -- twice over. Basil is
            # GREEN across the prep screen (prep only ever touches PLAYER units, so a green body is
            # invisible to Pick Units and costs no slot) and becomes the party's tenth unit the
            # moment the CUSA lands, on top of the nine the player chose, which is what the chapter
            # is priced for; a CUSA before the CALL would hand PREP a blue unit it never listed.
            # And the party she is talking TO does not exist on the field until prep places it.
            # Scene music follows vanilla Ch5's after-prep run (ADR 0336): the party's talk under
            # a lowered Advance (its 0x9BF), silence, Shadow of the Enemy for the one who will be
            # fought (Joshua's 0x9C3, Sahnar's scene 6), Distant Roads as the map begins (0x9C4).
            + '    MUSC(SONG_ADVANCE)\n    MUSI /* lowered under the party\'s talk */\n'
            + ch05_basil_join_block(basil_char)
            + '    CUSA(%s) /* green -> blue: she asked on box 3, and this is the answer */\n'
            % basil_char
            + '    MUNO\n    MUSCMID(SONG_SILENT)\n'
              '    MUSC(SONG_SHADOW_OF_THE_ENEMY) /* Sahnar, a person before she is a foe */\n'
            # Scene 6, LAST and on the map: the arena tile, the duelist standing on it, her own
            # scene before the player ever fights her. Vanilla's Joshua LOADs at this exact point
            # in its own beginning scene -- after the prep CALL -- which is what makes Sahnar a
            # turn-1 unit rather than a turn-2 riser (#25, Nicolas 2026-08-14).
            + ch05_sahnar_alone_block(sahnar_table, sahnar_char, None,
                                      ch05_sahnar_station(chap))
            + '    MUSC(SONG_DISTANT_ROADS) /* the map begins, as vanilla Ch5\'s 0x9C4 */\n'
            # Scene 7, and the map begins on its last word. The moose has been standing in the
            # turn-1 line since before prep, so this beat only has to look at it.
            + ch05_moose_charge_block(CH05_MOOSE_PID, ch05_moose_station(chap),
                                      ch05_party_camera_tile(chap))
            + '    ENUT(8)\n    EVBIT_T(7)\n    ENDA\n}')


def _vanilla_message_body(msg_id, source=None):
    """One committed vanilla message body, immune to the mutable injected text tree."""
    source = vanilla_decomp_text('texts/texts.txt') if source is None else source
    match = re.search(r'^## MSG_%03X\n(.*?)(?=\n\n## MSG_|\Z)' % msg_id,
                      source, re.M | re.S)
    if not match:
        sys.exit('ERROR: vanilla MSG_%03X is absent from texts/texts.txt at HEAD' % msg_id)
    return match.group(1).strip()


def _tutorial_plain_boxes(body):
    """Visible prose per [A] page, discarding FE text controls and layout padding."""
    boxes = []
    for page in body.split('[A]'):
        plain = re.sub(r'\[[^]]+\]', '', page)
        plain = ' '.join(plain.split())
        if plain:
            boxes.append(plain)
    return boxes


def ch05_arena_messages(chap):
    """The locked arena tutorial as vanilla's exact 1+5 message bodies.

    The YAML is the authored source; vanilla's committed messages are the layout template. The
    semantic comparison makes a future YAML edit fail rather than silently injecting stale prose,
    while the template preserves hand-placed line breaks, colour toggles and padding byte for byte.
    """
    event = next((e for e in chap.get('events', []) if e.get('trigger') == 'arena_tile_visited'),
                 None)
    if event is None:
        sys.exit('ERROR: ch05 has no arena_tile_visited tutorial event')
    authored = [_fe_dialogue_text(next(iter(box.values())))
                .replace('[red]', '').replace('[/red]', '') for box in event.get('script', [])]
    found = _vanilla_message_body(0x9D5)
    rules = _vanilla_message_body(0x9D6)
    vanilla_boxes = _tutorial_plain_boxes(found) + _tutorial_plain_boxes(rules)
    if authored != vanilla_boxes:
        sys.exit('ERROR: ch05 arena tutorial is locked to vanilla MSG_9D5 + MSG_9D6 verbatim; '
                 'YAML boxes differ: %r != %r' % (authored, vanilla_boxes))
    return found, rules


def ch05_ravisin_defeat_quote():
    """The displayed quote and unchanged flag that together drive ch05's boss win."""
    return defeat_quote_row(
        CH05_BOSS_PID, chapter_label_constant(CH05_HOST_INDEX),
        'Ravisin (ch05 boss): locked death quote -> DefeatBoss WIN flag',
        msg=CH05_RAVISIN_DEATH_MSG, flag='EVFLAG_DEFEAT_BOSS')


def ch05_ravisin_battle_quote():
    """The pair that plays Ravisin's taunt on first engagement, from either side (#25).

    Her weight comes from the orders scene, not from talking on the field, so this is FE8's
    own one-box mechanism and not a turn event: it fires on the FIGHT rather than on a clock.
    EVFLAG_BATTLE_QUOTES is deliberately not the win flag -- EVFLAG_DEFEAT_BOSS here would end
    the chapter the moment anybody swung at her.
    """
    return battle_quote_pair(
        CH05_BOSS_PID, chapter_label_constant(CH05_HOST_INDEX), CH05_RAVISIN_TAUNT_MSG,
        'Ravisin (ch05 boss): locked first-engagement taunt')


def ch05_wave_script(turn, wave_table):
    """Build one ch05 reinforcement script; only turn 2 speaks.

    The order carries the fiction: the arriving dead establish the escalation, then Ravisin
    names the reliquary race. Later waves are silent reinforcements and must not replay the
    warning.

    Sahnar is NOT one of these. She is on the map from turn 1 -- Ravisin raises her on screen
    in scene 3, and she LOADs after the prep CALL where vanilla LOADs Joshua (#25, Nicolas
    2026-08-14). The eruption is six reinforcements and a warning, and nothing else.
    """
    warning = ''
    if turn == 2:
        warning = (
            '    CUMO_CHAR(%s) /* Ravisin answers the party\'s pressure */\n'
            '    STAL(45)\n'
            '    CURE\n'
            '    TEXTSTART\n'
            '    TEXTSHOW(0x%X) /* the locked boxes: the reliquary race */\n'
            '    TEXTEND\n'
            '    REMA\n'
            % (CH05_BOSS_PID, CH05_ERUPTION_MSG))
    return ('{\n'
            '    LOAD1(0x1, %s)\n'
            '    ENUN\n'
            '%s'
            '    ENDA\n}' % (wave_table, warning))


def inject_ch05(campaign, boot=False, lupin_proof=False, moose_only=False,
                ending_arm=None, verbose=True):
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

    DEFERRED to follow-up passes: Basil's Talk-recruit prose, the opening/ending cutscenes
    (dialogue LOCKED in PR #196), and the title-card art. The four reliquary visits and arena
    tutorial are live. ch05's ending parks on the dev placeholder until ch06 hosts, exactly as
    ch04's did.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH05_CHAPTER_YAML)
    arena_wiring = ch05_arena_onboarding_wiring(chap)
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
    # --ch05-lupin ONLY: a one-unit table holding Lupin, LOADed BEFORE the opening's branch so
    # the ALIVE arm of scene 4 is reachable from a cold boot at all. It exists because a boot ROM
    # otherwise cannot walk that arm for two independent reasons, either of which alone is fatal:
    #   * the branch runs before LOMA while the party seed is LOADed after it, so gUnitArrayBlue
    #     is empty when CHECK_ALIVE asks (decisions.md -> "The --ch05-boot ROM can only ever play
    #     the NO-Lupin arm"); and
    #   * Lupin is not IN the seed -- it zips the cast against 9 deploy slots and he is last.
    # Loading before LOMA is safe: RestartBattleMap (bmio.c:1043) rebuilds map, BGs, sprites and
    # traps and never touches the unit arrays, so he survives as a roster entry, which is all
    # CHECK_ALIVE reads. He stands on the first deploy tile; PREP re-picks anyway.
    if lupin_proof:
        lupin = next((c for c in cast if c[0] == 'lupin'), None)
        if lupin is None:
            sys.exit('ERROR: --ch05-lupin: no `lupin` in ch05\'s cast, so the proof ROM would '
                     'film the same no-Lupin arm as the plain boot and quietly prove nothing')
        _uid, lslot, lce, ldce, llevel = lupin
        declare_unit_table(
            CH05_LUPIN_PROOF_TABLE,
            [_ally_unit_entry(leader, lslot, ldce, llevel, slots[0][0], slots[0][1],
                              ', '.join(CLASS_LOADOUT[lce]),
                              ' /* Lupin -- --ch05-lupin proof/film ROM only */')],
            'ch05 --ch05-lupin: Lupin alone, LOADed before the opening branch so CHECK_ALIVE '
            'finds him and scene 4 plays its ALIVE arm')

    # Sahnar is a turn-1 unit now (#25), so she matches the `arrives_turn: None` selector the
    # line table uses -- but she must stay OUT of it, because she LOADs from her own table at
    # her own beat and the line goes down in one LOAD1 before prep.
    line_rows = ch05_enemy_rows(chap, exclude=('sahnar',))
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
    # Sahnar rides her own table so scene 6 (and Basil's Talk) can address her alone -- a shared
    # pid is unaddressable, which is exactly what #203 cost ch04's wolf pack. She selects on the
    # turn-1 `arrives_turn: None` now, not the eruption's 2: Ravisin summons her ON SCREEN in
    # scene 3 and she LOADs after the prep CALL, where vanilla LOADs Joshua (#25).
    sahnar_rows = ch05_enemy_rows(chap, exclude=frozenset(
        e['id'] for e in chap['enemy_units'] if e['id'] != 'sahnar'))
    if len(sahnar_rows) != 1:
        sys.exit('ERROR: ch05 expects exactly one Sahnar on the turn-1 board, got %d -- she is '
                 'summoned in scene 3 and must not carry an arrives_turn' % len(sahnar_rows))
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
    # The Talk id is ch05's OWN now (step 5 writes the locked scene into it), so this passes on
    # the holder == chapter branch rather than on the placeholder one. Kept anyway: it is the gate
    # that catches a re-point into a neighbour's block, which is exactly how the Basil join beat
    # once ended up on 0x9C2 -- ch04's own no-parley ending.
    assert_message_id_unclaimed(CH05_SAHNAR_TALK_MSG, 'ch05', "Basil's Talk recruit of Sahnar")
    assert_message_id_unclaimed(CH05_SAHNAR_TALK_NO_LUPIN_MSG, 'ch05',
                                "the Talk recruit's no-Lupin arm")
    sahnar_rows = [row.replace(CH05_GENERIC_PID, sahnar_char, 1) for row in sahnar_rows]
    declare_unit_table(CH05_SAHNAR_TABLE, sahnar_rows,
                       'ch05 Sahnar: summoned HOSTILE in scene 3, on the arena from turn 1; '
                       'Basil Talks her over (#25)')

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
        # Her WALK-OFF tile, not her load tile: she rises on the arena and immediately steps off
        # it (ch05_sahnar_station), so the escort Basil has to survive is measured to where
        # Sahnar actually stands and fights.
        must_reach=ch05_sahnar_station(chap)[1])
    # The moose is ch04's creature under a ch05 pid, and a pid is what the sprite tables are
    # keyed on -- so this is the check that it is an ELK here and not CLASS_GWYLLGI's hound.
    assert_custom_art_pid_wired(CH05_MOOSE_PID, 'white-moose', 'ch05')
    # Same check for the BOSS, and for the same failure: without an override row her raw pid
    # falls through GetUnitSMSId to CLASS_DRUID's stock sprite -- the hooded MAN she stopped
    # being when her battle anim landed, while her own committed sheets sit unused (#25).
    assert_custom_art_pid_wired(CH05_BOSS_PID, 'ravisin', 'ch05')
    # Scene 7's charge is MOVE_DEFINED + ENUN, so a leg the moose cannot WALK would hang the
    # chapter on the last beat before turn 1 -- ch04's own soft-lock, on the same animal. Every
    # waypoint is checked from where the run BEGINS, not from the pen: the run starts in the
    # top-right corner and row 0's walkable stretch is only x=10..14.
    _pen, _from, _route = ch05_moose_station(chap)
    for _leg in _route:
        assert_scripted_move_reachable(maps_dir, CH05_LAYOUT[1], _from, _leg,
                                       CH04_MOOSE_MOV_TABLE, 'the white moose (ch05 scene 7)')
    bx, by = CH05_BASIL_GREEN_POS
    declare_unit_table(CH05_BASIL_TABLE, [_ally_unit_entry(
        leader, basil[1], basil[3], basil[4], bx, by, ', '.join(CLASS_LOADOUT[basil[2]]),
        ' /* basil -- green until the opening join beat CUSAs her blue (#25) */',
        allegiance=basil_faction)],
        'ch05 Basil: %s at the pocket mouth; the opening join makes her the escort'
        % basil_faction)
    # Sahnar is Joshua and Basil is Natasha, so Sahnar has to play the way Joshua plays -- and
    # half of how Joshua plays is a REFUSAL. His AI_A_07 will not swing at the cleric walking up
    # to talk him down, which is the only reason a fragile escort can reach a Killing Edge on
    # the arena tile at all. That refusal rides a character id in a global list, not in the .ai
    # bytes, so copying his bytes alone leaves Basil a legal target. Repointed here, at the one
    # place that knows who our escort is.
    assert_escort_safe_ai_has_one_client(enemy_ai_initialiser(
        chap, next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')))
    repoint_escort_safe_ai_list(basil_char, 'Basil (ch05 escort)')

    # 3. Wire ours into the host slot's event group; every list not named here is written empty.
    turn_rows = ''.join(
        '    TurnEventPlayer(0, %s, %d) /* eruption wave: %d */\n'
        % (CH05_WAVE_SCRIPTS[turn], turn, wave_counts[turn])
        for turn in sorted(CH05_WAVE_TABLES))
    # The race's two tile states: a reliquary DESECRATED by a raider, and one closed behind the
    # party. Must run AFTER _retarget_host_chapter zeroed changeLayerId (as ch04's does).
    _inject_tile_changes('MS_Ch05MapChanges', ch05_map_changes(chap, maps_dir), CH05_HOST_INDEX)
    # Character = the Basil->Sahnar Talk, and nothing else -- structurally identical to vanilla
    # Ch5's single CHAR(NATASHA, JOSHUA). Recruiter set is Sahnar's own `parley.by` (Basil), the
    # gated flavour of the shared flow; ch03's Trex passes the whole roster instead. No
    # pre_script: unlike ch04's pack parley there is no group to bring over with her.
    sahnar_char_events, sahnar_talk_script = talk_recruit_wiring(
        parley_recruiters(next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')),
        sahnar_char, CH05_SAHNAR_TALK_FLAG, CH05_SAHNAR_TALK_SCRIPT, CH05_SAHNAR_TALK_MSG,
        # Proof #1 is a wolf ch04's optional parley may never have handed the player, so the
        # scene asks the roster and shows the other copy when he is not on it (#25).
        variant=(CH05_LUPIN_CHARACTER, CH05_SAHNAR_TALK_NO_LUPIN_MSG))
    # The roster is OUR table, not vanilla Ch6's: before the group pointed at it, ch05 ran
    # vanilla Ch6's ally table -- the party deployed on another map's coordinates, four of them
    # inside walls, with PREP running and the load-test PASSing.
    write_event_group('ch05', CH05_EVENTINFO_H, CH05_EVENT_GROUP, lists={
        'turnBasedEvents': '{\n' + turn_rows + '    END_MAIN\n}',
        # Misc = the win/lose machinery. DefeatBoss is an AFEV on EVFLAG_DEFEAT_BOSS, which
        # Ravisin's FLAGGED defeat quote sets on her death (step 5) -- CA_BOSS alone fires nothing.
        'miscBasedEvents': arena_wiring['misc'],
        # Location = the four reliquary visits + the elven store. The shops are wired for good (a
        # shop needs no script and no text); the visits own their rewards, and each carries its
        # CH05_VILLAGE_FLAGS event id -- the race (#25).
        'locationBasedEvents': ch05_location_events(chap),
        'characterBasedEvents': sahnar_char_events,
    }, roster=CH05_ALLY_TABLE, scenes=(CH05_BEGINNING_SCRIPT, CH05_ENDING_SCRIPT))

    # 4. Beginning scene + the wave scripts. LOMA rebuilds the battle map fresh, the line
    #    LOADs, then CALL Preparations (which reads the never-LOADed cap template).
    with open(CH05_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    seed_load = ('    LOAD1(0x1, %s) /* --ch05-boot: found an armed party */\n'
                 '    ENUN\n' % CH05_BOOT_SEED_TABLE) if boot else ''
    # --ch05-lupin: put Lupin on the roster BEFORE the opening runs, so scene 4's CHECK_ALIVE
    # finds him and the ALIVE arm plays. Proof/film ROM ONLY -- the real chain needs nothing
    # here, because ReadGameSave has filled gUnitArrayBlue before the chapter's events run.
    lupin_load = ('    LOAD1(0x1, %s) /* --ch05-lupin: the alive arm needs a live Lupin */\n'
                  '    ENUN\n' % CH05_LUPIN_PROOF_TABLE) if lupin_proof else ''
    script = _replace_brace_block(
        script, CH05_BEGINNING_SCRIPT + '[] =',
        ch05_beginning_script(chap, basil_char, CH05_SAHNAR_TABLE, sahnar_char,
                              seed_load, lupin_load, moose_only=moose_only,
                              ending_arm=ending_arm),
        CH05_EVENTSCRIPT_H)
    for turn in sorted(CH05_WAVE_TABLES):
        script = _replace_brace_block(
            script, CH05_WAVE_SCRIPTS[turn] + '[] =',
            ch05_wave_script(turn, CH05_WAVE_TABLES[turn]),
            CH05_EVENTSCRIPT_H)
    # The ending: the save-all-four payout, then the win. ch06 is not hosted yet, so the win
    # lands on the dev placeholder exactly as ch03's did until ch04 hosted (chain_ch04_to_ch05
    # advances the real path below).
    script = _replace_brace_block(script, CH05_ENDING_SCRIPT + '[] =',
                                  ch05_ending_script(chap, basil_char, sahnar_char),
                                  CH05_EVENTSCRIPT_H)
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
        'ch05 Basil Talks Sahnar down -- the locked recruit scene at 0x%X (or its no-Lupin arm '
        'at 0x%X), then CUSA red->blue'
        % (CH05_SAHNAR_TALK_MSG, CH05_SAHNAR_TALK_NO_LUPIN_MSG))
    for symbol, body, comment in arena_wiring['scripts']:
        declare_event_script(CH05_EVENTSCRIPT_H, symbol, body, comment)
    assert_event_scripts_defined(
        CH05_EVENTSCRIPT_H, [slot[0] for slot in CH05_VILLAGE_SLOTS.values()]
        + [CH05_SAHNAR_TALK_SCRIPT]
        + [symbol for symbol, _body, _comment in arena_wiring['scripts']])

    # 5. Texts + the flagged defeat quote that IS the win trigger.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + (boss.get('fe_name') or boss['name'])))
    set_message_body(lines, host['goal']['windowTextId'], goal_window_body('Defeat boss'))
    set_message_body(lines, CH05_ERUPTION_MSG, ch05_eruption_message(chap))
    set_message_body(lines, CH05_RAVISIN_DEATH_MSG, ch05_ravisin_death_message(chap))
    set_message_body(lines, CH05_RAVISIN_TAUNT_MSG, ch05_ravisin_taunt_message(chap))
    for msg_id, body in ch05_sahnar_talk_messages(chap):
        set_message_body(lines, msg_id, body)
    for msg_id, body in ch05_ending_messages(chap):
        set_message_body(lines, msg_id, body)
    for msg_id, body in (ch05_opening_messages(chap) + ch05_basil_join_messages(chap)
                         + ch05_sahnar_alone_message(chap) + ch05_moose_charge_message(chap)):
        set_message_body(lines, msg_id, body)
    for msg_id, body in arena_wiring['messages']:
        set_message_body(lines, msg_id, body)
    # The four reliquary visits (#25). Each site's speaker is one of the tomb's risen dead, over
    # BG_HOUSE -- a full-screen backdrop, wrapped at the same talk budget as the BG scenes, not at
    # the on-map bubble. One `visit_text` entry per BOX, ch04's lesson: the authored A-press
    # breaks are the pacing (27 boxes against vanilla Ch5's own 26), and a flowed scalar would
    # reflow them to wherever the pixel budget runs out.
    for village in chap['villages']:
        _symbol, msg, fid = CH05_VILLAGE_SLOTS[village['id']]
        set_message_body(lines, msg, _script_to_message(
            [{who: line} for who, line in village_boxes(village)],
            {DEFAULT_VILLAGE_SPEAKER: ('[OpenMidLeft]', fid)}))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    _write_chapter_title_card(host, 'Ch.5: ' + chap['title'])
    # Keep the already-proven flag path and make its quote visible now that Ravisin's portrait
    # and host-owned message both exist. SetPidDefeatedFlag still fires EVFLAG_DEFEAT_BOSS;
    # DisplayDefeatTalkForPid now shows the one locked box before the ending AFEV runs.
    _prepend_defeat_quote(ch05_ravisin_defeat_quote())
    # Scene 12: the taunt on first engagement. A separate list and a separate flag from the
    # death quote above -- the player meets her twice, and each meeting has its own box.
    _prepend_battle_quote(ch05_ravisin_battle_quote())

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
