"""Chapter 4 (#24): its injector and everything only it reads.
"""
import os
import sys

from inject import engine_hooks
from inject.cast import _classed_cast, char_symbol, CLASS_LOADOUT, PORTRAIT_MAP
from inject.chapter_ids import (
    CH04_ENDING_MSG, CH04_ENDING_NO_LUPIN_MSG, CH04_GOAL_STATUS_MSG, CH04_GOAL_WINDOW_MSG,
    CH04_LUPIN_TALK_MSG, CH04_MOOSE_MOV_TABLE, CH04_MOOSE_MSG, CH04_MOOSE_PID, CH04_NIMSY_FID,
    CH04_OPENING_CARD_MSG, CH04_OPENING_FOREST_BG, CH04_OPENING_MSGS, CH04_REVEAL_MSGS,
    CH04_VILLAGE_SLOTS)
from inject.decomp import _replace_brace_block, REPO
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter
from inject.hosts import CH02_HOST_INDEX, CH04_EVENT_GROUP, CH04_HOST_INDEX
from inject.maps import (
    _inject_tile_changes, _map_changes_tileset, _register_chapter_map, _snowy_metatile_for)
from inject.paths import (
    CH4_EVENTSCRIPT_H, CH5_EVENTINFO_H, CH5_EVENTSCRIPT_H, EVENTS_UDEFS_C, TEXTS_TXT)
from inject.recruit import (
    assert_custom_art_pid_wired, on_map_talk_recruits, parley_recruiters, talk_recruit_wiring)
from inject.scenes import (
    _branch_on_slot_c, _emit_scene_beats, _make_fid, _scenic_beat_calls, _split_event_beats,
    _write_chapter_title_card, variant_beat)
from inject.terrain import assert_scripted_move_reachable, reda_route_move
from inject.text import (
    _fid_tag, _script_to_message, dev_placeholder_scene, goal_window_body, name_message_body,
    set_message_body)
from inject.units import (
    _ally_unit_entry, _deploy_cap_entries, _enemy_unit_entry, enemy_ai_initialiser)
from inject.villages import (
    assert_village_gifts_match_vanilla, assert_village_tiles_visitable, DEFAULT_VILLAGE_SPEAKER,
    location_events, village_boxes, village_reward_item, village_script)


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
# Stage 2b -- the turn-2 wolf-pack reveal + Marty->Lupin parley (issue #24). Lupin rides the
# collision-free Duessel identity slot (Stage 2a); placed RED as the pack leader, Marty's Talk
# CUSAs him blue and CUSNs the surviving generics green where they stand. The symbols/ids below
# are DEAD vanilla Ch5 slots -- unreachable once inject_ch04 blanks the Ch5 event lists, so we
# repurpose them (the same idiom ch03 uses for its dead-Ch4 block; each verified free by grep).
CH04_LUPIN_TALK_SCRIPT = 'EventScr_089F2340'  # dead Ch5 script -> the parley event
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
CH04_PARLEY_LABEL_BASE = 0x40   # one skip label per wolf. The talk script HAS carried labels of
                                # its own since ch05's Talk grew a no-Lupin branch (0 and 1), so
                                # this is no longer "the only labels here" -- it is a base that
                                # must stay clear of talk_recruit_script's own `label_base`.
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
CH04_REVEAL_CAMERA = (2, 2)                      # centre on the NW pack cluster
# Scene BGs. The cottage is vanilla FE8's House1 hearth interior and Nimsy rides the vanilla
# old-lady generic mug -- both DECIDED 2026-07-04 (Nicolas): in-ROM, so no vendored asset, no
# injection, no credit line. Beat B plays over a fogged plain (the scout who cannot see).
CH04_OPENING_COTTAGE_BG = 'BG_HOUSE'            # vanilla House1 -- Nimsy's hearth
                                               # vanilla's bg_Plain_1 tiles on a winter palette
                                               # (BG_PLAIN_1_FOG is a GREEN meadow; the vanilla
                                               # "_FOG" variants are palette swaps, not art)
CH04_ENDING_BG = 'BG_FOREST'                    # dusk at the treeline; the sled at the ridge
# The moose: a scripted NEUTRAL that is sighted once and gone. It rides its own dead Ch5 slots.
CH04_MOOSE_SCRIPT = 'EventScr_089F2270'         # dead Ch5 script (vanilla's Natasha/Joshua Talk;
                                                #   its only ref is the Ch5 Character list, which
                                                #   inject_ch04 replaces) -> the moose-flees beat
CH04_MOOSE_SYMBOL = 'UnitDef_088B58D8'          # dead Ch5 unit table (referenced only from
CH04_MOOSE_GUARD_FLAG = 'EVFLAG_TMP(10)'        # AREA one-shot guard (must differ from the talk flag)
CH04_MOOSE_CLASS = 'CLASS_GWYLLGI'              # geometry token: the 32x32 quadruped wait row
# (SCRIPTED_NEUTRAL_SPRITES lives in inject/cast.py: it is a CROSS-CHAPTER registry and its
#  rows name pids from more than one chapter.)
# Where the party first SEES it: the mid-map clearing, on the tomb-side (NE) half of the 15x15
# map. Its authored YAML route then crosses the east bridge and exits to the southeast.
CH04_MOOSE_POS = (11, 4)
CH04_MOOSE_AREA = (9, 2, 14, 7)                 # AREA(x1, y1, x2, y2) -- the clearing it watches from.
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


def branch_on_flag(flag, if_set, if_clear, label_base=0):
    """A vanilla-shaped event branch: run `if_set` when `flag` is set, else `if_clear`.

    The FE8 idiom (cf. ch19a's ending, which picks its text by CHECK_EVENTID + CHECK_ALIVE):
    CHECK_EVENTID leaves the flag in slot C. ch04's ending picks its no-Lupin variant this way.
    """
    return _branch_on_slot_c('CHECK_EVENTID(%s)' % flag, if_set, if_clear,
                             label_base, 'flag clear')


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


def ch04_location_events(chap):
    """ch04's Location list. Vanilla Ch4 wires two villages and so do we (#24); no shops."""
    return location_events(chap.get('villages', []),
                           {vid: slot[0] for vid, slot in CH04_VILLAGE_SLOTS.items()})


def ch04_map_changes(chap, maps_dir):
    """ch04's tile flips (#214): the snag falling into a crossing, and each visited village
    closing its door.

    Returns the `map_changes_asm` change list. Both are vanilla Ch4's own changes, kept at
    vanilla's positions (our retile preserved them) but resolved to OUR tileset's metatiles by
    terrain. Without the village entry a visited village stays looking un-visited, which vanilla
    never does."""
    tileset = _map_changes_tileset(maps_dir, CH04_LAYOUT)
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
    move = reda_route_move(pid, flee_route, 'continuous route over the bridge, then southeast',
                           who='the white moose')
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
        for index, (x, y) in enumerate(enemy['positions']):
            ai = enemy_ai_initialiser(chap, enemy, index)
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


def _ch04_wave_pack_kit(chap, wave):
    """(class_enum, ai, items) for a ch04 enemy wave, read from its authored YAML (no drift).

    The pack keeps this kit through the parley: CUSN changes a unit's FACTION, nothing else,
    so the converted wolves fight on with the same class, items and AI -- which is the point,
    since "the wolves turn the tide" is what the parley buys."""
    cls = CH04_CLASS_IDS[wave['class']]
    ai = enemy_ai_initialiser(chap, wave)
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
    cls, ai, items = _ch04_wave_pack_kit(chap, wave)
    leader_pos, generic_pos = wave['positions'][0], wave['positions'][1:]
    if len(generic_pos) != len(CH04_PACK_PIDS):
        sys.exit('ERROR: ch04 pack is %d generics but CH04_PACK_PIDS has %d pids -- the '
                 'parley converts BY PID, so every wolf needs one'
                 % (len(generic_pos), len(CH04_PACK_PIDS)))
    _uid, slot, class_enum, deploy_class, level = lupin
    lupin_row = _enemy_unit_entry(
        char_symbol(slot), deploy_class, level, False,
        leader_pos[0], leader_pos[1], ', '.join(CLASS_LOADOUT[class_enum]),
        ai,
        ' /* lupin -- hostile pack leader (red; Marty parleys him blue) */')
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

    # Fog is NOT set here any more: ch04 declares `fog: 3` in its own YAML and
    # `apply_chapter_fog` writes every hosted chapter's declaration (#365). The literal that
    # used to sit here is the reason -- "ch04 is a fogged chapter" was a fact about the
    # chapter recorded only inside its injector. Same argument as the battle GROUND, which is
    # declared once in CHAPTER_BATTLE_TILESETS because the chapters left standing on vanilla
    # grass were exactly the ones no injector had written a line for.

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
    assert_custom_art_pid_wired(CH04_MOOSE_PID, 'white-moose', 'ch04')
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
    # ON-MAP -- same talk-bubble budget as the moose beat (one budget now; see fe8_talk_font).
    _, reveal_beats = _split_event_beats(chap, 'wolf_pack_reveal', 'ch04 turn-2 reveal',
                                         msg_ids=CH04_REVEAL_MSGS, card_required=False)
    _emit_scene_beats(lines, CH04_REVEAL_MSGS, reveal_beats, cut_fid,
                      {'lupin': '[OpenMidRight]', 'marty': '[OpenMidLeft]'})
    # Stage 4 scene bodies. The opening + both endings play over a BG (full-screen window, wrap
    # the talk budget); the moose beat is ON-MAP and takes the same one (a wider line hits
    # PutTalkBubble's unclamped right-side branch and runs off the tilemap -- the ch03 crier bug).
    set_message_body(lines, CH04_OPENING_CARD_MSG, name_message_body(op_card))
    _emit_scene_beats(lines, CH04_OPENING_MSGS, op_beats, cut_fid, op_home)
    _emit_scene_beats(lines, (CH04_MOOSE_MSG,), moose_beats, cut_fid, {})
    # Both endings stage as a two-shot: the trail-reader holds mid-right, Marty answers from
    # mid-left. Lupin already owns mid-right in the parley, so he keeps it here; on the no-parley
    # path PINKY inherits both the podium and the job (his opening beat was failing to see
    # through the fog, so finding the trail once it thins pays that off). Without these anchors
    # every box defaults to mid-left and each speaker fades the last one out mid-scene.
    end_home = {'lupin': '[OpenMidRight]', 'pinky': '[OpenMidRight]',
                'meesmickle': '[OpenFarLeft]'}
    _emit_scene_beats(lines, (CH04_ENDING_MSG,), end_beats, cut_fid, end_home)
    _emit_scene_beats(lines, (CH04_ENDING_NO_LUPIN_MSG,), [end_beat_no_lupin],
                      cut_fid, end_home)
    # The village lines (#205, #24). The axe door is Nimsy herself, wearing the vanilla old-lady
    # mug the opening already gave her; the forest cottage is a logger who never opens up, on
    # vanilla's own snag-village mug. Both play over BG_NORMAL_VILLAGE (full-screen window), so
    # they take the same talk budget as every other faced scene.
    #
    # One `visit_text` entry per BOX: consecutive turns by one speaker coalesce into a single
    # [OpenX] block with each entry's pages kept whole, so the authored beats survive as the
    # A-press breaks instead of being reflowed into wherever the pixel budget runs out.
    for village in chap['villages']:
        _symbol, msg, fid, _bg = CH04_VILLAGE_SLOTS[village['id']]
        set_message_body(lines, msg, _script_to_message(
            [{who: line} for who, line in village_boxes(village)],
            {DEFAULT_VILLAGE_SPEAKER: ('[OpenMidLeft]', fid)}))
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
